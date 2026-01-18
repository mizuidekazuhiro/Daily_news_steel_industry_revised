import requests

from src.config.env import SERPER_API_KEY


def search_serper(query):
    try:
        res = requests.post(
            "https://google.serper.dev/news",
            headers={
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "q": query,
                "num": 500,
                "timeRange": "d1",
                "hl": "en",
            },
            timeout=30,
        )
        if res.status_code == 402:
            return "SERPER_CREDIT_ERROR"
        res.raise_for_status()
        return res.json().get("news", [])
    except requests.RequestException:
        return "SERPER_CREDIT_ERROR"
