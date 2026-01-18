import json
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from src.domain.time_utils import parse_publish_datetime


def extract_source_from_url(url):
    try:
        domain = urlparse(url).netloc
        return domain.replace("www.", "")
    except ValueError:
        return "Unknown"


def _extract_meta_published(soup, reference_time):
    meta_keys = {
        "article:published_time",
        "og:published_time",
        "pubdate",
        "publish_date",
        "date",
        "dc.date",
        "dc.date.issued",
        "datepublished",
    }
    for tag in soup.find_all("meta"):
        key = (tag.get("property") or tag.get("name") or "").lower()
        if key in meta_keys:
            content = tag.get("content")
            published = parse_publish_datetime(content, reference_time)
            if published:
                return published
    return None


def _extract_jsonld_published(soup, reference_time):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or "{}")
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "@graph" in payload:
            nodes = payload.get("@graph", [])
        else:
            nodes = payload if isinstance(payload, list) else [payload]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            published = node.get("datePublished") or node.get("dateModified")
            published_dt = parse_publish_datetime(published, reference_time)
            if published_dt:
                return published_dt
    return None


def fetch_article(url, reference_time):
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")

        paragraphs = []
        for p in soup.find_all("p"):
            t = p.get_text().strip()
            if len(t) < 30:
                continue
            if any(x in t for x in ["会員", "登録", "利用規約", "著作権", "JavaScript", "Cookie", "広告"]):
                continue
            paragraphs.append(t)

        body = "\n".join(paragraphs)
        published_dt = _extract_meta_published(soup, reference_time)
        published_source = "meta"
        if not published_dt:
            published_dt = _extract_jsonld_published(soup, reference_time)
            published_source = "jsonld"
        if not published_dt:
            published_source = "unknown"

        return body, published_dt, body[:3000], published_source
    except requests.RequestException:
        return None, None, None, None


def classify_article(article):
    text = (article["title"] + article["body"]).lower()

    if any(k in text for k in ["stock", "share", "株価", "target price", "52-week", "analyst"]):
        return "STOCK"
    if any(k in text for k in ["investment", "plant", "capacity", "million ton", "工場", "設備", "増設"]):
        return "BUSINESS"
    if any(k in text for k in ["hydrogen", "decarbon", "green steel", "cbam", "低炭素", "脱炭素"]):
        return "GREEN"
    return "OTHER"
