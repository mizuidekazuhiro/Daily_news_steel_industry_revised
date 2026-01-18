
## `main.py`
```python
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
from src.config.prompts import load_prompts
from src.config.settings import load_settings
from src.domain.time_utils import (
    now_utc,
    format_dt_jst,
    parse_publish_datetime,
    is_within_hours,
)
from src.usecases.score_articles import apply_scores


def main():
    settings = load_settings()
    prompts = load_prompts()
    targets, enterprise_targets, google_alert_rss = load_targets()

    reference_time = now_utc()
    today_str = reference_time.strftime("%Y%m%d")
    hours = settings.get("limits", {}).get("hours", 24)
    max_articles = settings.get("limits", {}).get("max_articles_per_label", 5)

    scorer = RuleBasedScorer.from_yaml()

    fetch_fx_rates()
    notice_html = """
    <div style="font-family:'Meiryo UI', sans-serif; font-size:12px; color:#666; margin-bottom:16px;">
    ※本メールはAIにより自動生成しています。内容の正確性については、必ず原文記事等により別途ご確認ください。
    </div>
    """

    sections = ""
    all_articles_for_summary = {}
    no_article_labels = []

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

                body, scraped_dt = fetch_article(a.get("link"), reference_time)
                if not body:
                    continue

                final_dt = scraped_dt or serper_dt
                if not is_within_hours(final_dt, reference_time, hours=hours):
                    continue

                articles.append({
                    "title": a.get("title", ""),
                    "body": body,
                    "url": a.get("link", ""),
                    "date": format_dt_jst(final_dt),
                    "source": a.get("source", ""),
                    "final_dt": final_dt,
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

            articles.extend(alert_articles[:need])

        apply_scores(articles, scorer)
        articles.sort(
            key=lambda x: (x.get("score", 0), x["final_dt"]),
            reverse=True,
        )

        if articles:
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

    final_html = (
        notice_html
        + generate_morning_summary(all_articles_for_summary, prompts.get("morning_summary_user", ""))
        + sections
        + generate_stock_section()
    )

    send_mail(final_html, f"Daily report｜鉄鋼ニュース記事纏め_{today_str}")


if __name__ == "__main__":
    main()
