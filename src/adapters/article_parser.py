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
        scraped_dt = parse_publish_datetime(soup.get_text(), reference_time)

        return body, scraped_dt, body[:3000]
    except requests.RequestException:
        return None, None, None


def classify_article(article):
    text = (article["title"] + article["body"]).lower()

    if any(k in text for k in ["stock", "share", "株価", "target price", "52-week", "analyst"]):
        return "STOCK"
    if any(k in text for k in ["investment", "plant", "capacity", "million ton", "工場", "設備", "増設"]):
        return "BUSINESS"
    if any(k in text for k in ["hydrogen", "decarbon", "green steel", "cbam", "低炭素", "脱炭素"]):
        return "GREEN"
    return "OTHER"
