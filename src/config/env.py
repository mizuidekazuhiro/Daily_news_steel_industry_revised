import os

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_ARTICLES_DB_ID = os.getenv("NOTION_ARTICLES_DB_ID")
NOTION_DAILY_DB_ID = os.getenv("NOTION_DAILY_DB_ID")
NOTION_TARGETS_DB_ID = os.getenv("NOTION_TARGETS_DB_ID")
NOTION_RULES_DB_ID = os.getenv("NOTION_RULES_DB_ID")

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "").lower() in ("1", "true", "yes")
