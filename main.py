import logging
import re
import time
from collections import defaultdict

from src.adapters.article_parser import fetch_article, classify_article
from src.adapters.email_notifier import send_mail
from src.adapters.google_alert_source import (
    fetch_google_alert_articles,
    dedup_alert_articles,
)

from src.adapters.openai_summarizer import summarize_with_gpt, generate_morning_summary
from src.adapters.serper_source import search_serper
from src.adapters.yahoo_finance import fetch_fx_rates, generate_stock_section
from src.adapters.notion_client import NotionClient
from src.adapters.notion_exporter import NotionExporter
from src.adapters.notion_rules import fetch_rules_from_notion
from src.adapters.notion_targets import fetch_targets_from_notion, build_targets_map
from src.adapters.notion_audit import write_audit_log
from src.config import env
from src.config.notion import load_notion_config
from src.config.prompts import load_prompts
from src.config.settings import load_settings
from src.domain.article_dedup import deduplicate_articles
from src.domain.time_utils import (
    now_utc,
    format_dt_jst,
    parse_publish_datetime,
    parse_publish_datetime_from_url,
    ensure_aware_utc,
    JST,
    compute_lookback_window,
    is_within_window,
)
from src.usecases.score_articles import apply_scores
from src.usecases.summary_select import (
    select_summary_articles,
    importance_value,
    extract_hard_exclusion_rules,
    apply_hard_exclusion,
    sort_for_summary,
)
from src.domain.rule_engine import build_rules
from src.usecases.tag_articles import apply_tags, load_tag_rules
from src.usecases.target_coverage import build_processing_labels, summarize_target_coverage


def apply_diversity_limits_for_global_summary(articles, targets_by_label, top_n):
    """Pick top articles with per-label caps (Enterprise=1, Theme=2 by default)."""
    picked = []
    label_counts = defaultdict(int)

    for article in articles:
        label = article.get("target_label") or article.get("label")
        target_info = targets_by_label.get(label, {})
        max_pick = target_info.get("max_pick")
        if max_pick is None:
            # Default limits: Enterprise=1, Theme=2
            is_enterprise = target_info.get("enterprise", False)
            max_pick = 1 if is_enterprise else 2

        if max_pick <= 0:
            continue
        if label_counts[label] >= max_pick:
            continue

        # Respect the per-label limit while keeping score order.
        picked.append(article)
        label_counts[label] += 1
        if len(picked) >= top_n:
            break

    return picked


def main():
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    notion_config = load_notion_config()
    prompts = load_prompts()
    required_notion_env = {
        "NOTION_TOKEN": "Notion APIへ接続するために必要です。",
        "NOTION_TARGETS_DB_ID": "監視対象（Targets DB）を読み込むために必要です。",
        "NOTION_RULES_DB_ID": "重要度ルール（Rules DB）を読み込むために必要です。",
        "NOTION_ARTICLES_DB_ID": "記事ログを保存するために必要です。",
        "NOTION_DAILY_DB_ID": "日次サマリを保存するために必要です。",
    }
    missing_notion_env = [name for name in required_notion_env if not getattr(env, name)]
    if missing_notion_env:
        details = "\n".join(f"- {name}: {required_notion_env[name]}" for name in missing_notion_env)
        raise RuntimeError(
            "Notion連携に必要な環境変数が不足しています。以下を設定してください。\n"
            f"{details}"
        )

    notion_client = NotionClient(env.NOTION_TOKEN)
    logging.info("Notion integration enabled")

    target_entries = fetch_targets_from_notion(notion_client, env.NOTION_TARGETS_DB_ID)
    targets, _, google_alert_rss, targets_by_label = build_targets_map(target_entries)
    labels = build_processing_labels(targets, google_alert_rss)
    target_stats = summarize_target_coverage(labels, targets, google_alert_rss)
    logging.info(
        "Targets loaded: labels=%d serper_queries=%d rss_feeds=%d rss_only=%d serper_only=%d",
        target_stats["labels"],
        target_stats["serper_queries"],
        target_stats["rss_feeds"],
        target_stats["rss_only"],
        target_stats["serper_only"],
    )

    reference_time = now_utc()
    today_str = reference_time.strftime("%Y%m%d")
    run_id = reference_time.strftime("%Y%m%dT%H%M%SZ")
    hours = settings.get("limits", {}).get("hours", 24)
    max_articles = settings.get("limits", {}).get("max_articles_per_label", 5)
    openai_settings = settings.get("openai", {})
    label_openai_settings = openai_settings.get("label_summary", {})
    morning_openai_settings = openai_settings.get("morning_summary", {})

    run_time_jst = reference_time.astimezone(JST)
    window_start_jst, window_end_jst = compute_lookback_window(run_time_jst)
    weekend_mode = run_time_jst.weekday() == 0
    logging.info(
        "Run window (JST): start=%s end=%s weekday=%s",
        window_start_jst.isoformat(),
        window_end_jst.isoformat(),
        run_time_jst.weekday(),
    )
    if weekend_mode:
        logging.info("Weekend mode enabled: collecting Friday-Sunday articles")

    tag_rules = load_tag_rules()
    notion_rules = []
    notion_exporter = None
    try:
        notion_rules = fetch_rules_from_notion(notion_client, env.NOTION_RULES_DB_ID)
    except Exception as exc:
        write_audit_log(
            {"run_id": run_id, "url": "", "step": "fetch_rules_failed", "error": str(exc)},
        )
        logging.exception("Failed to load Notion rules")

    notion_exporter = NotionExporter(
        notion_client,
        env.NOTION_ARTICLES_DB_ID,
        env.NOTION_DAILY_DB_ID,
        run_id,
        notion_config=notion_config,
    )
    logging.info("Notion exporter configured for articles and daily summary")

    fetch_fx_rates()
    engine_rules = build_rules(notion_rules)
    hard_exclusion_rules = extract_hard_exclusion_rules(engine_rules)
    notice_html = """
    <div style="font-family:'Meiryo UI','Meiryo',sans-serif; font-size:12px; color:#666; margin-bottom:16px;">
    ※本メールはAIにより自動生成しています。内容の正確性については、必ず原文記事等により別途ご確認ください。
    </div>
    """

    sections = []
    all_scored_articles = []
    no_article_labels = []
    notion_article_page_ids = []
    total_articles = 0
    notion_failures = 0

    for label in labels:
        queries = targets.get(label, [])
        articles = []

        date_stats = {
            "scraped_date_used": 0,
            "serper_date_used": 0,
            "url_date_used": 0,
            "missing_published_at": 0,
            "outside_window": 0,
            "missing_samples": [],
            "outside_window_samples": [],
            "serper_date_samples": [],
        }

        for q in queries:
            search_result = search_serper(q)
            if search_result == "SERPER_CREDIT_ERROR":
                break

            for a in search_result:
                url = a.get("link", "")
                serper_raw = a.get("date")
                serper_dt = parse_publish_datetime(serper_raw, reference_time)
                body, scraped_dt, body_excerpt, fetched_published_source = fetch_article(url, reference_time)
                if not body:
                    continue

                scraped_dt = ensure_aware_utc(scraped_dt)
                url_dt = parse_publish_datetime_from_url(url, reference_time)

                if scraped_dt:
                    final_dt = scraped_dt
                    published_source = fetched_published_source or "scraped"
                    date_stats["scraped_date_used"] += 1
                elif serper_dt:
                    final_dt = ensure_aware_utc(serper_dt)
                    published_source = "serper"
                    date_stats["serper_date_used"] += 1
                    if len(date_stats["serper_date_samples"]) < 5:
                        date_stats["serper_date_samples"].append(serper_raw)
                elif url_dt:
                    final_dt = ensure_aware_utc(url_dt)
                    published_source = "url"
                    date_stats["url_date_used"] += 1
                else:
                    final_dt = None
                    published_source = "missing"

                if not final_dt:
                    date_stats["missing_published_at"] += 1
                    if len(date_stats["missing_samples"]) < 5:
                        date_stats["missing_samples"].append(url)
                    logging.warning(
                        "Skipping article with missing published_at: label=%s title=%s url=%s serper_date=%s source=%s",
                        label,
                        a.get("title", ""),
                        url,
                        serper_raw,
                        a.get("source", ""),
                    )
                    continue

                articles.append({
                    "title": a.get("title", ""),
                    "body": body_excerpt,
                    "body_full": body,
                    "body_preview": body_excerpt,
                    "url": a.get("link", ""),
                    "date": format_dt_jst(final_dt),
                    "source": a.get("source", ""),
                    "final_dt": final_dt,
                    "published_at": final_dt.isoformat(),
                    "published_source": published_source or "unknown",
                    "type": classify_article({
                        "title": a.get("title", ""),
                        "body": body
                    }),
                    "target_label": label,
                })

        articles.sort(key=lambda x: x["final_dt"], reverse=True)

        rss_feeds = google_alert_rss.get(label, [])
        if rss_feeds and len(articles) < max_articles:
            need = max_articles - len(articles)

            alert_articles = fetch_google_alert_articles(
                label,
                google_alert_rss,
                reference_time,
                hours=hours,
                window_start=window_start_jst,
                window_end=window_end_jst,
            )
            alert_articles = dedup_alert_articles(articles, alert_articles)
            for article in alert_articles:
                article["date"] = format_dt_jst(article["final_dt"])
                if not article.get("published_at"):
                    article["published_at"] = article["final_dt"].isoformat()
                if not article.get("published_source"):
                    article["published_source"] = "unknown"
                article["target_label"] = label

            articles.extend(alert_articles[:need])

        before_window_filter = len(articles)
        outside_window_urls = []
        filtered_articles = []
        for article in articles:
            if is_within_window(article.get("final_dt"), window_start_jst, window_end_jst):
                filtered_articles.append(article)
            else:
                date_stats["outside_window"] += 1
                if len(outside_window_urls) < 5:
                    outside_window_urls.append(article.get("url", ""))
        articles = filtered_articles
        date_stats["outside_window_samples"] = outside_window_urls

        logging.info(
            "Window filter label=%s before=%d after=%d",
            label,
            before_window_filter,
            len(articles),
        )
        latest_final_dt = articles[0].get("final_dt") if articles else None
        oldest_final_dt = articles[-1].get("final_dt") if articles else None
        logging.info(
            "Date stats label=%s scraped=%d serper=%d url=%d missing=%d outside_window=%d latest=%s oldest=%s",
            label,
            date_stats["scraped_date_used"],
            date_stats["serper_date_used"],
            date_stats["url_date_used"],
            date_stats["missing_published_at"],
            date_stats["outside_window"],
            latest_final_dt.isoformat() if latest_final_dt else None,
            oldest_final_dt.isoformat() if oldest_final_dt else None,
        )
        if date_stats["missing_samples"]:
            logging.info("Missing published_at samples label=%s urls=%s", label, date_stats["missing_samples"])
        if date_stats["outside_window_samples"]:
            logging.info("Outside window samples label=%s urls=%s", label, date_stats["outside_window_samples"])

        if any(k in label for k in ["国内鉄筋", "電炉", "鉄筋電炉"]):
            logging.info(
                "Rebar/EAF diagnostics label=%s before_window_filter=%d after_window_filter=%d missing_published_at_count=%d outside_window_count=%d top_missing_urls=%s top_outside_window_urls=%s top_serper_dates=%s",
                label,
                before_window_filter,
                len(articles),
                date_stats["missing_published_at"],
                date_stats["outside_window"],
                date_stats["missing_samples"][:5],
                date_stats["outside_window_samples"][:5],
                date_stats["serper_date_samples"][:5],
            )

        apply_scores(articles, notion_rules=notion_rules)
        deduped_articles, dedup_stats = deduplicate_articles(articles)
        all_articles_for_storage = deduped_articles
        articles_for_summary, hard_excluded_articles = apply_hard_exclusion(deduped_articles, hard_exclusion_rules)

        all_articles_for_storage.sort(
            key=lambda x: (x.get("score", 0), x.get("final_dt")),
            reverse=True,
        )
        articles_for_summary = sort_for_summary(articles_for_summary)
        negative_included_count = sum(1 for a in articles_for_summary if importance_value(a) < 0)
        target_max_pick = (targets_by_label.get(label, {}) or {}).get("max_pick")
        label_pick_limit = int(max_articles or 5)

        logging.info(
            "Label filter stats label=%s before_dedup_count=%d after_dedup_count=%d removed_by_normalized_url=%d removed_by_normalized_title=%d removed_by_body_similarity=%d hard_excluded_count=%d negative_score_included_count=%d summary_candidate_count=%d selected_for_label_summary_count=%d label_pick_limit=%d target_max_pick=%s max_articles_per_label=%d selected_titles=%s selected_scores=%s selected_urls=%s hard_exclusion_reasons=%s",
            label,
            dedup_stats["before_dedup_count"],
            dedup_stats["after_dedup_count"],
            dedup_stats["removed_by_normalized_url"],
            dedup_stats["removed_by_normalized_title"],
            dedup_stats["removed_by_body_similarity"],
            len(hard_excluded_articles),
            negative_included_count,
            len(articles_for_summary),
            len(articles_for_summary[:label_pick_limit]),
            label_pick_limit,
            target_max_pick,
            int(max_articles or 5),
            [a.get("title", "") for a in articles_for_summary[:label_pick_limit]],
            [importance_value(a) for a in articles_for_summary[:label_pick_limit]],
            [a.get("url", "") for a in articles_for_summary[:label_pick_limit]],
            [a.get("hard_exclusion_reasons", []) for a in hard_excluded_articles],
        )
        if dedup_stats.get("merge_details"):
            for detail in dedup_stats["merge_details"]:
                logging.debug(
                    "Dedup merged label=%s reason=%s removed=%s kept=%s",
                    label,
                    detail.get("reason"),
                    detail.get("removed_title"),
                    detail.get("kept_title"),
                )
        if all_articles_for_storage:
            all_scored_articles.extend(articles_for_summary)
            for article in all_articles_for_storage:
                article["label"] = label
                apply_tags(article, tag_rules, notion_rules=notion_rules)
                if notion_exporter:
                    try:
                        page_id = notion_exporter.upsert_article(article)
                        article["notion_page_id"] = page_id
                        notion_article_page_ids.append(page_id)
                        logging.info("Notion article upserted: %s", page_id)
                    except Exception:
                        notion_failures += 1
                        logging.exception("Failed to export article to Notion: %s", article.get("url"))
            if articles_for_summary:
                sections.append({
                    "label": label,
                    "score": articles_for_summary[0].get("score", 0),
                    "html": summarize_with_gpt(
                        label,
                        articles_for_summary[:label_pick_limit],
                        articles_for_summary[:label_pick_limit],
                        prompts.get("summarize_system", ""),
                        label_openai_settings,
                    ),
                })
                total_articles += len(articles_for_summary[:label_pick_limit])
            else:
                no_article_labels.append(label)
        else:
            no_article_labels.append(label)

        time.sleep(1)

    sections.sort(key=lambda item: item["score"], reverse=True)
    sections_html = "".join(section["html"] for section in sections)
    if no_article_labels:
        joined = "、".join(no_article_labels)
        sections_html += f"""
        <div style="font-family:'Meiryo UI','Meiryo',sans-serif; padding:16px; color:#777; font-size:13px; border-bottom:1px solid #ddd;">
            該当記事なし企業一覧：{joined}
        </div><br>
        """

    # Build diversified TopN for the global summary (morning section).
    global_summary_top_n = settings.get("limits", {}).get("global_summary_top_n", 12)
    summary_candidates = select_summary_articles(
        all_scored_articles,
        exclude_types=["stock"],
    )
    summary_candidates.sort(
        key=lambda x: (importance_value(x), x.get("final_dt")),
        reverse=True,
    )
    diversified_articles = apply_diversity_limits_for_global_summary(
        summary_candidates,
        targets_by_label,
        global_summary_top_n,
    )
    logging.info(
        "Global summary selection: global_summary_top_n=%d candidates=%d diversified=%d",
        global_summary_top_n,
        len(summary_candidates),
        len(diversified_articles),
    )
    morning_summary_html = generate_morning_summary(
        diversified_articles,
        prompts.get("morning_summary_user", ""),
        morning_openai_settings,
    )
    final_html_body = (
        notice_html
        + morning_summary_html
        + sections_html
        + generate_stock_section()
    )
    final_html = f"""<div style="font-family:'Meiryo UI','Meiryo',sans-serif;">{final_html_body}</div>"""

    send_mail(final_html, f"Daily report｜鉄鋼ニュース記事纏め_{today_str}")

    if notion_exporter:
        summary_text = re.sub(r"<br>", "\n", morning_summary_html)
        summary_text = re.sub(r"<[^>]+>", "", summary_text).strip()
        run_date = reference_time.astimezone(JST).date().isoformat()
        run_stats = f"articles_saved={len(notion_article_page_ids)}, total_articles={total_articles}, notion_failures={notion_failures}"
        try:
            summary_article_page_ids = [
                article.get("notion_page_id")
                for article in diversified_articles
                if article.get("notion_page_id")
            ]
            notion_exporter.create_daily_summary(
                run_date,
                summary_text,
                summary_article_page_ids,
                run_stats=run_stats,
            )
            logging.info("Notion daily summary created for %s", run_date)
        except Exception:
            logging.exception("Failed to create daily summary in Notion")


if __name__ == "__main__":
    main()
