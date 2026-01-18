import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StockBot/1.0)"
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

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
