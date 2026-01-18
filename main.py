
## `main.py`
```python
import logging
import re
import time

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
from src.config import env
from src.config.prompts import load_prompts
from src.config.settings import load_settings
from src.domain.time_utils import (
    now_utc,
    format_dt_jst,
    parse_publish_datetime,
    is_within_hours,
    JST,
)
from src.usecases.score_articles import apply_scores
from src.usecases.tag_articles import apply_tags, load_tag_rules


def main():
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    prompts = load_prompts()
    targets, enterprise_targets, google_alert_rss = load_targets()

    reference_time = now_utc()
    today_str = reference_time.strftime("%Y%m%d")
    run_id = reference_time.strftime("%Y%m%dT%H%M%SZ")
    hours = settings.get("limits", {}).get("hours", 24)
    max_articles = settings.get("limits", {}).get("max_articles_per_label", 5)

    scorer = RuleBasedScorer.from_yaml()
    tag_rules = load_tag_rules()
    notion_exporter = None
    if env.NOTION_TOKEN and env.NOTION_ARTICLES_DB_ID and env.NOTION_DAILY_DB_ID:
        notion_client = NotionClient(env.NOTION_TOKEN)
        notion_exporter = NotionExporter(
            notion_client,
            env.NOTION_ARTICLES_DB_ID,
            env.NOTION_DAILY_DB_ID,
            run_id,
        )

    fetch_fx_rates()
    notice_html = """
    <div style="font-family:'Meiryo UI', sans-serif; font-size:12px; color:#666; margin-bottom:16px;">
    ※本メールはAIにより自動生成しています。内容の正確性については、必ず原文記事等により別途ご確認ください。
    </div>
    """

    sections = ""
    all_articles_for_summary = {}
    no_article_labels = []
    notion_article_page_ids = []

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

                body, scraped_dt, body_excerpt = fetch_article(a.get("link"), reference_time)
                if not body:
                    continue

                final_dt = scraped_dt or serper_dt
                if not is_within_hours(final_dt, reference_time, hours=hours):
                    continue

                articles.append({
                    "title": a.get("title", ""),
                    "body": body_excerpt,
                    "body_full": body,
                    "url": a.get("link", ""),
                    "date": format_dt_jst(final_dt),
                    "source": a.get("source", ""),
                    "final_dt": final_dt,
                    "published_at": final_dt.isoformat(),
                    "published_source": "serper",
                    "type": classify_article({
                        "title": a.get("title", ""),
                        "body": body
                    }),
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
                article["published_at"] = article["final_dt"].isoformat()
                article["published_source"] = "unknown"

            articles.extend(alert_articles[:need])

        apply_scores(articles, scorer)
        articles.sort(
            key=lambda x: (x.get("score", 0), x["final_dt"]),
            reverse=True,
        )

        if articles:
            for article in articles:
                article["label"] = label
                apply_tags(article, tag_rules)
                if notion_exporter:
                    try:
                        page_id = notion_exporter.upsert_article(article)
                        notion_article_page_ids.append(page_id)
                    except Exception:
                        logging.exception("Failed to export article to Notion: %s", article.get("url"))
            sections += summarize_with_gpt(
                label,
                articles[:max_articles],
                prompts.get("summarize_system", ""),
            )
            all_articles_for_summary[label] = articles[:max_articles]
        else:
            no_article_labels.append(label)

        time.sleep(1)

    if no_article_labels:
        joined = "、".join(no_article_labels)
        sections += f"""
        <div style="font-family:'Meiryo UI', sans-serif; padding:16px; color:#777; font-size:13px; border-bottom:1px solid #ddd;">
            該当記事なし企業一覧：{joined}
        </div><br>
        """

    morning_summary_html = generate_morning_summary(
        all_articles_for_summary,
        prompts.get("morning_summary_user", ""),
    )
    final_html = (
        notice_html
        + morning_summary_html
        + sections
        + generate_stock_section()
    )

    send_mail(final_html, f"Daily report｜鉄鋼ニュース記事纏め_{today_str}")

    if notion_exporter:
        summary_text = re.sub(r"<br>", "\n", morning_summary_html)
        summary_text = re.sub(r"<[^>]+>", "", summary_text).strip()
        run_date = reference_time.astimezone(JST).date().isoformat()
        try:
            notion_exporter.create_daily_summary(run_date, summary_text, notion_article_page_ids)
        except Exception:
            logging.exception("Failed to create daily summary in Notion")


if __name__ == "__main__":
    main()
