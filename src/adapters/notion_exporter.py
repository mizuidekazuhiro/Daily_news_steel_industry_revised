import re

from src.adapters.notion_audit import write_audit_log
from src.domain.notion_utils import compute_article_id, compute_body_hash, normalize_url


def truncate_text(text, max_len):
    if not text:
        return ""
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= max_len:
        return normalized
    if max_len <= 1:
        return "…" if max_len == 1 else ""
    return normalized[: max_len - 1].rstrip() + "…"


def make_short_summary(text, limit=1200):
    if not text:
        return ""
    if len(text) <= limit:
        return text
    delimiters = ["\n\n", "\n", "。", ".", " "]
    for delimiter in delimiters:
        index = text.rfind(delimiter, 0, limit + 1)
        if index > 0:
            candidate = text[: index + len(delimiter)].rstrip()
            if candidate:
                if len(candidate) >= limit:
                    candidate = candidate[: max(limit - 1, 0)].rstrip()
                return f"{candidate}…"
    if limit <= 1:
        return "…" if limit == 1 else ""
    return f"{text[: limit - 1].rstrip()}…"


def split_for_notion_blocks(text, chunk_size=1800):
    if not text:
        return []
    chunks = []
    current = ""

    def flush_current():
        nonlocal current
        if current:
            chunks.append(current)
            current = ""

    def append_line(line, separator):
        nonlocal current
        candidate = f"{current}{separator}{line}" if current else line
        if len(candidate) > chunk_size:
            flush_current()
            if len(line) > chunk_size:
                for i in range(0, len(line), chunk_size):
                    chunks.append(line[i : i + chunk_size])
                return
            current = line
        else:
            current = candidate

    paragraphs = text.split("\n\n")
    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            flush_current()
            for line in paragraph.split("\n"):
                append_line(line, "\n")
            flush_current()
        else:
            append_line(paragraph, "\n\n")
    flush_current()
    return chunks


def build_paragraph_blocks(chunks):
    blocks = []
    for chunk in chunks:
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}],
                },
            }
        )
    return blocks


def chunk_text(text, chunk_size):
    if not text:
        return []
    chunks = []
    current = ""
    for line in text.splitlines():
        if len(line) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(line), chunk_size):
                chunks.append(line[i : i + chunk_size])
            continue
        candidate = f"{current}\n{line}".strip() if current else line
        if len(candidate) > chunk_size:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def build_children_blocks(full_text, chunk_size=1800):
    blocks = []
    for chunk in chunk_text(full_text, chunk_size):
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}],
                },
            }
        )
    return blocks


class NotionExporter:
    DEFAULT_ARTICLE_PROPERTIES = {
        "name": {"name": "Name", "type": "title"},
        "url": {"name": "URL", "type": "url"},
        "source": {"name": "Source", "type": "rich_text"},
        "label": {"name": "Label", "type": "select"},
        "type": {"name": "Type", "type": "select"},
        "country": {"name": "Country", "type": "multi_select"},
        "sector": {"name": "Sector", "type": "multi_select"},
        "primary_country": {"name": "PrimaryCountry", "type": "select"},
        "importance": {"name": "Importance", "type": "select"},
        "importance_score": {"name": "ImportanceScore", "type": "number"},
        "importance_reasons": {"name": "ImportanceReasons", "type": "rich_text"},
        "published_at": {"name": "PublishedAt", "type": "date"},
        "published_source": {"name": "PublishedSource", "type": "select"},
        "article_id": {"name": "ArticleId", "type": "rich_text"},
        "normalized_url": {"name": "NormalizedURL", "type": "url"},
        "body_hash": {"name": "BodyHash", "type": "rich_text"},
        "body_preview": {"name": "BodyPreview", "type": "rich_text"},
    }
    DEFAULT_DAILY_PROPERTIES = {
        "name": {"name": "Name", "type": "title"},
        "run_id": {"name": "RunId", "type": "rich_text"},
        "run_date": {"name": "RunDate", "type": "date"},
        "morning_summary": {"name": "MorningSummary", "type": "rich_text"},
        "articles": {"name": "Articles", "type": "relation"},
        "run_stats": {"name": "RunStats", "type": "rich_text"},
    }
    FULL_SUMMARY_MARKER = "## Morning Summary (Full)"

    def __init__(
        self,
        notion_client,
        articles_db_id,
        daily_db_id,
        run_id,
        audit_log_path="logs/notion_audit.jsonl",
        notion_config=None,
    ):
        self.client = notion_client
        self.articles_db_id = articles_db_id
        self.daily_db_id = daily_db_id
        self.run_id = run_id
        self.audit_log_path = audit_log_path
        notion_config = notion_config or {}
        self.auto_heading = notion_config.get("auto_heading", "[AUTO]")
        self.article_properties = notion_config.get("articles", {}).get("properties", {})
        self.daily_properties = notion_config.get("daily", {}).get("properties", {})

    def _log_error(self, url, reason, error):
        write_audit_log(
            {
                "run_id": self.run_id,
                "url": url,
                "step": reason,
                "error": str(error),
            },
            path=self.audit_log_path,
        )

    def _get_property_config(self, key, defaults):
        config = defaults.get(key, {})
        override = self.article_properties.get(key) if defaults is self.DEFAULT_ARTICLE_PROPERTIES else self.daily_properties.get(key)
        if override:
            if isinstance(override, dict):
                name = override.get("name", config.get("name"))
                prop_type = override.get("type", config.get("type"))
                return {"name": name, "type": prop_type}
            if isinstance(override, str):
                return {"name": override, "type": config.get("type")}
        return config

    def _property_name(self, key, defaults):
        config = self._get_property_config(key, defaults)
        return config.get("name")

    def _set_property(self, properties, key, value, defaults):
        config = self._get_property_config(key, defaults)
        name = config.get("name")
        prop_type = config.get("type")
        if not name or not prop_type:
            return
        if prop_type == "title":
            properties[name] = {"title": [{"text": {"content": value or ""}}]}
        elif prop_type == "url":
            properties[name] = {"url": value or None}
        elif prop_type == "rich_text":
            properties[name] = {"rich_text": [{"text": {"content": value or ""}}]} if value else {"rich_text": []}
        elif prop_type == "select":
            properties[name] = {"select": {"name": value}} if value else {"select": None}
        elif prop_type == "multi_select":
            properties[name] = {"multi_select": [{"name": v} for v in value or []]}
        elif prop_type == "number":
            properties[name] = {"number": float(value) if value is not None else None}
        elif prop_type == "date":
            properties[name] = {"date": {"start": value}} if value else {"date": None}
        elif prop_type == "relation":
            properties[name] = {"relation": [{"id": v} for v in value or []]}

    def _build_article_properties(self, article, normalized_url, article_id, body_hash, body_preview):
        label = article.get("label")
        article_type = article.get("type")
        importance = article.get("importance")
        published_source = article.get("published_source", "unknown")
        published_at = article.get("published_at")
        importance_reasons = article.get("importance_reasons") or ""
        if isinstance(importance_reasons, list):
            importance_reasons = "; ".join(importance_reasons)
        properties = {}
        self._set_property(properties, "name", article.get("title", ""), self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "url", article.get("url", ""), self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "source", article.get("source", ""), self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "label", label, self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "type", article_type, self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "country", article.get("country_tags", []), self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "sector", article.get("sector_tags", []), self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "primary_country", article.get("primary_country"), self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "importance", importance, self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "importance_score", article.get("importance_score", 0), self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "importance_reasons", importance_reasons, self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "published_at", published_at, self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "published_source", published_source, self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "article_id", article_id, self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "normalized_url", normalized_url, self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "body_hash", body_hash, self.DEFAULT_ARTICLE_PROPERTIES)
        self._set_property(properties, "body_preview", body_preview, self.DEFAULT_ARTICLE_PROPERTIES)
        return properties

    def _find_article_page(self, article_id):
        property_name = self._property_name("article_id", self.DEFAULT_ARTICLE_PROPERTIES) or "ArticleId"
        payload = {
            "filter": {
                "property": property_name,
                "rich_text": {"equals": article_id},
            }
        }
        data = self.client.query_database(self.articles_db_id, payload)
        results = data.get("results", [])
        return results[0] if results else None

    def _full_summary_exists(self, page_id):
        cursor = None
        while True:
            response = self.client.list_block_children(page_id, start_cursor=cursor)
            for block in response.get("results", []):
                if block.get("type") != "paragraph":
                    continue
                rich_text = block.get("paragraph", {}).get("rich_text", [])
                content = "".join(item.get("plain_text", "") for item in rich_text)
                if self.FULL_SUMMARY_MARKER in content:
                    return True
            if not response.get("has_more"):
                return False
            cursor = response.get("next_cursor")

    def _append_full_summary(self, page_id, summary_text):
        if not summary_text or self._full_summary_exists(page_id):
            return
        chunks = split_for_notion_blocks(summary_text, 1800)
        blocks = build_paragraph_blocks([self.FULL_SUMMARY_MARKER] + chunks)
        self.client.append_block_children(page_id, {"children": blocks})

    def upsert_article(self, article):
        normalized_url = normalize_url(article.get("url", ""))
        article_id = compute_article_id(normalized_url)
        body_sources = [
            article.get("body_full"),
            article.get("content"),
            article.get("body"),
            article.get("body_preview"),
        ]
        body_text = max((text or "" for text in body_sources), key=len)
        body_hash = compute_body_hash(body_text)
        body_preview = truncate_text(body_text, 800)
        if not article_id:
            error = ValueError("ArticleId is empty")
            self._log_error(article.get("url", ""), "missing_article_id", error)
            raise error
        try:
            page = self._find_article_page(article_id)
            properties = self._build_article_properties(article, normalized_url, article_id, body_hash, body_preview)
            if page:
                page_id = page["id"]
                self.client.update_page(page_id, {"properties": properties})
                return page_id
            payload = {
                "parent": {"database_id": self.articles_db_id},
                "properties": properties,
            }
            children = build_children_blocks(body_text)
            if children:
                payload["children"] = children
            created = self.client.create_page(payload)
            page_id = created["id"]
            return page_id
        except Exception as exc:
            self._log_error(article.get("url", ""), "upsert_article_failed", exc)
            raise

    def create_daily_summary(self, run_date, morning_summary, article_page_ids, run_stats=None):
        try:
            properties = {}
            self._set_property(
                properties,
                "name",
                f"Daily Summary {run_date}",
                self.DEFAULT_DAILY_PROPERTIES,
            )
            self._set_property(properties, "run_id", self.run_id, self.DEFAULT_DAILY_PROPERTIES)
            self._set_property(properties, "run_date", run_date, self.DEFAULT_DAILY_PROPERTIES)
            short_text = make_short_summary(morning_summary)
            self._set_property(properties, "morning_summary", short_text, self.DEFAULT_DAILY_PROPERTIES)
            self._set_property(properties, "articles", article_page_ids, self.DEFAULT_DAILY_PROPERTIES)
            self._set_property(properties, "run_stats", run_stats, self.DEFAULT_DAILY_PROPERTIES)
            payload = {
                "parent": {"database_id": self.daily_db_id},
                "properties": properties,
            }
            created = self.client.create_page(payload)
            page_id = created["id"]
            self._append_full_summary(page_id, morning_summary)
            return page_id
        except Exception as exc:
            self._log_error("", "create_daily_summary_failed", exc)
            raise
