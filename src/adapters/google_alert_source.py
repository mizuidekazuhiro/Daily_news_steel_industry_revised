import re
import urllib.parse

import feedparser

from src.domain.time_utils import parse_publish_datetime, is_within_hours
from src.adapters.article_parser import fetch_article, classify_article, extract_source_from_url


def normalize_google_alert_url(url):
    if not url:
        return url

    if "google.com/url" not in url:
        return url

    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)

    if "url" in qs:
        return qs["url"][0]

    if "q" in qs:
        return qs["q"][0]

    return url


def fetch_google_alert_articles(label, google_alert_rss, reference_time, hours=24):
    articles = []

    rss_urls = google_alert_rss.get(label, [])
    if not rss_urls:
        return articles

    for rss_url in rss_urls:
        feed = feedparser.parse(rss_url)

        for e in feed.entries:
            title = e.get("title", "")
            raw_url = e.get("link", "")
            url = normalize_google_alert_url(raw_url)

            published = parse_publish_datetime(e.get("published"), reference_time)
            body, scraped_dt, body_excerpt = fetch_article(url, reference_time)
            if not body:
                continue

            final_dt = scraped_dt or published
            if not is_within_hours(final_dt, reference_time, hours=hours):
                continue

            articles.append({
                "title": title,
                "body": body_excerpt,
                "body_full": body,
                "url": url,
                "date": None,
                "source": extract_source_from_url(url),
                "final_dt": final_dt,
                "type": classify_article({
                    "title": title,
                    "body": body
                }),
            })

    articles.sort(key=lambda x: x["final_dt"], reverse=True)
    return articles


def dedup_alert_articles(serper_articles, alert_articles):
    serper_keys = set(
        re.sub(r"\W+", "", a["title"].lower())[:50]
        for a in serper_articles
    )

    results = []
    for a in alert_articles:
        key = re.sub(r"\W+", "", a["title"].lower())[:50]
        if key in serper_keys:
            continue
        results.append(a)

    return results
