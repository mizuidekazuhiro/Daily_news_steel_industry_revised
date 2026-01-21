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
from src.adapters.rule_based_scorer import RuleBasedScorer
from src.adapters.serper_source import search_serper
from src.adapters.targets_yaml import load_targets
from src.adapters.yahoo_finance import fetch_fx_rates, generate_stock_section
from src.adapters.notion_client import NotionClient
from src.adapters.notion_exporter import NotionExporter
from src.adapters.notion_rules import fetch_rules_from_notion
from src.adapters.notion_audit import write_audit_log
from src.config import env
from src.config.notion import load_notion_config
from src.config.prompts import load_prompts
from src.config.settings import load_settings
from src.domain.time_utils import (
    now_utc,
    format_dt_jst,
    parse_publish_datetime,
    is_within_hours,
    ensure_aware_utc,
    JST,
)
from src.usecases.score_articles import apply_scores
from src.usecases.summary_select import select_summary_articles, importance_value
from src.usecases.tag_articles import apply_tags, load_tag_rules


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
    targets, enterprise_targets, google_alert_rss, targets_by_label = load_targets()

    reference_time = now_utc()
    today_str = reference_time.strftime("%Y%m%d")
    run_id = reference_time.strftime("%Y%m%dT%H%M%SZ")
    hours = settings.get("limits", {}).get("hours", 24)
    max_articles = settings.get("limits", {}).get("max_articles_per_label", 5)

    scorer = RuleBasedScorer.from_yaml()
    tag_rules = load_tag_rules()
    notion_rules = []
    notion_exporter = None
    notion_client = None
    if env.NOTION_TOKEN:
        notion_client = NotionClient(env.NOTION_TOKEN)
        logging.info("Notion integration enabled: token found")
    else:
        logging.info("Notion integration disabled: NOTION_TOKEN is missing")
    if notion_client and env.NOTION_RULES_DB_ID:
        try:
            notion_rules = fetch_rules_from_notion(notion_client, env.NOTION_RULES_DB_ID)
        except Exception as exc:
            write_audit_log(
                {"run_id": run_id, "url": "", "step": "fetch_rules_failed", "error": str(exc)},
            )
            logging.exception("Failed to load Notion rules")
    elif notion_client:
        logging.info("Notion rules disabled: NOTION_RULES_DB_ID is missing")
    if notion_client and env.NOTION_ARTICLES_DB_ID and env.NOTION_DAILY_DB_ID:
        notion_exporter = NotionExporter(
            notion_client,
            env.NOTION_ARTICLES_DB_ID,
            env.NOTION_DAILY_DB_ID,
            run_id,
            notion_config=notion_config,
        )
        logging.info("Notion exporter configured for articles and daily summary")
    elif notion_client:
        missing = []
        if not env.NOTION_ARTICLES_DB_ID:
            missing.append("NOTION_ARTICLES_DB_ID")
        if not env.NOTION_DAILY_DB_ID:
            missing.append("NOTION_DAILY_DB_ID")
        logging.info("Notion exporter disabled: missing %s", ", ".join(missing))

    fetch_fx_rates()
    notice_html = """
    <div style="font-family:'Meiryo UI', sans-serif; font-size:12px; color:#666; margin-bottom:16px;">
    ※本メールはAIにより自動生成しています。内容の正確性については、必ず原文記事等により別途ご確認ください。
    </div>
    """

    sections = []
    all_scored_articles = []
    no_article_labels = []
    notion_article_page_ids = []
    total_articles = 0
    notion_failures = 0

    for label, queries in targets.items():
        articles = []

        for q in queries:
            search_result = search_serper(q)
            if search_result == "SERPER_CREDIT_ERROR":
                break

            for a in search_result:
                serper_dt = parse_publish_datetime(a.get("date"), reference_time)
                if not is_within_hours(serper_dt, reference_time, hours=hours):
                    continue

                body, scraped_dt, body_excerpt, published_source = fetch_article(a.get("link"), reference_time)
                if not body:
                    continue

                final_dt = ensure_aware_utc(scraped_dt or serper_dt)
                if not is_within_hours(final_dt, reference_time, hours=hours):
                    continue

                if not scraped_dt:
                    published_source = "serper"
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

        if label in enterprise_targets and len(articles) < max_articles:
            need = max_articles - len(articles)

            alert_articles = fetch_google_alert_articles(
                label,
                google_alert_rss,
                reference_time,
                hours=hours,
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

        apply_scores(articles, scorer, notion_rules=notion_rules)
        articles.sort(
            key=lambda x: (x.get("score", 0), x["final_dt"]),
            reverse=True,
        )

        if articles:
            all_scored_articles.extend(articles)
            for article in articles:
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
            sections.append({
                "label": label,
                "score": articles[0].get("score", 0),
                "html": summarize_with_gpt(
                    label,
                    articles[:max_articles],
                    articles[:max_articles],
                    prompts.get("summarize_system", ""),
                ),
            })
            total_articles += len(articles[:max_articles])
        else:
            no_article_labels.append(label)

        time.sleep(1)

    sections.sort(key=lambda item: item["score"], reverse=True)
    sections_html = "".join(section["html"] for section in sections)
    if no_article_labels:
        joined = "、".join(no_article_labels)
        sections_html += f"""
        <div style="font-family:'Meiryo UI', sans-serif; padding:16px; color:#777; font-size:13px; border-bottom:1px solid #ddd;">
            該当記事なし企業一覧：{joined}
        </div><br>
        """

    # Build diversified TopN for the global summary (morning section).
    global_summary_top_n = settings.get("limits", {}).get("global_summary_top_n", 10)
    summary_candidates = select_summary_articles(
        all_scored_articles,
        min_importance=0,
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
    morning_summary_html = generate_morning_summary(
        diversified_articles,
        prompts.get("morning_summary_user", ""),
    )
    final_html = (
        notice_html
        + morning_summary_html
        + sections_html
        + generate_stock_section()
    )

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
