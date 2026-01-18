from src.adapters.notion_audit import write_audit_log
from src.domain.notion_utils import compute_article_id, compute_body_hash, normalize_url, split_text_blocks


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

    def _build_article_properties(self, article, normalized_url, article_id, body_hash):
        label = article.get("label")
        article_type = article.get("type")
        importance = article.get("importance")
        published_source = article.get("published_source", "unknown")
        published_at = article.get("published_at")
        importance_reasons = article.get("importance_reasons") or ""
        if isinstance(importance_reasons, list):
            importance_reasons = "; ".join(importance_reasons)
        body_preview = article.get("body_preview") or article.get("body") or ""
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

    def _find_auto_heading_block(self, page_id):
        start_cursor = None
        while True:
            children = self.client.list_block_children(page_id, start_cursor=start_cursor)
            for block in children.get("results", []):
                block_type = block.get("type")
                if block_type and block_type.startswith("heading_"):
                    rich_text = block.get(block_type, {}).get("rich_text", [])
                    text = "".join(t.get("plain_text", "") for t in rich_text)
                    if text.strip() == self.auto_heading:
                        return block
            if not children.get("has_more"):
                break
            start_cursor = children.get("next_cursor")
        return None

    def _ensure_auto_heading(self, page_id):
        existing = self._find_auto_heading_block(page_id)
        if existing:
            return existing.get("id")
        payload = {
            "children": [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": self.auto_heading}}],
                        "is_toggleable": True,
                    },
                }
            ]
        }
        created = self.client.append_block_children(page_id, payload)
        results = created.get("results", [])
        return results[0].get("id") if results else None

    def _clear_auto_blocks(self, block_id):
        if not block_id:
            return
        start_cursor = None
        while True:
            children = self.client.list_block_children(block_id, start_cursor=start_cursor)
            for block in children.get("results", []):
                self.client.delete_block(block["id"])
            if not children.get("has_more"):
                break
            start_cursor = children.get("next_cursor")

    def _append_body_blocks(self, block_id, body_text):
        chunks = split_text_blocks(body_text)
        for i in range(0, len(chunks), 100):
            slice_blocks = chunks[i:i + 100]
            payload = {
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": chunk}}]
                        },
                    }
                    for chunk in slice_blocks
                ]
            }
            self.client.append_block_children(block_id, payload)

    def upsert_article(self, article):
        normalized_url = normalize_url(article.get("url", ""))
        article_id = compute_article_id(normalized_url)
        body_hash = compute_body_hash(article.get("body_full", ""))
        body_text = article.get("body_full", "")
        if not article_id:
            error = ValueError("ArticleId is empty")
            self._log_error(article.get("url", ""), "missing_article_id", error)
            raise error
        try:
            page = self._find_article_page(article_id)
            properties = self._build_article_properties(article, normalized_url, article_id, body_hash)
            if page:
                page_id = page["id"]
                current_hash = ""
                body_hash_name = self._property_name("body_hash", self.DEFAULT_ARTICLE_PROPERTIES) or "BodyHash"
                body_hash_prop = page.get("properties", {}).get(body_hash_name, {})
                if body_hash_prop.get("type") == "rich_text":
                    current_hash = "".join(t.get("plain_text", "") for t in body_hash_prop.get("rich_text", []))
                self.client.update_page(page_id, {"properties": properties})
                if current_hash != body_hash:
                    auto_block_id = self._ensure_auto_heading(page_id)
                    self._clear_auto_blocks(auto_block_id)
                    if body_text:
                        self._append_body_blocks(auto_block_id or page_id, body_text)
                return page_id
            payload = {
                "parent": {"database_id": self.articles_db_id},
                "properties": properties,
            }
            created = self.client.create_page(payload)
            page_id = created["id"]
            if body_text:
                auto_block_id = self._ensure_auto_heading(page_id)
                self._append_body_blocks(auto_block_id or page_id, body_text)
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
            self._set_property(properties, "morning_summary", morning_summary, self.DEFAULT_DAILY_PROPERTIES)
            self._set_property(properties, "articles", article_page_ids, self.DEFAULT_DAILY_PROPERTIES)
            self._set_property(properties, "run_stats", run_stats, self.DEFAULT_DAILY_PROPERTIES)
            payload = {
                "parent": {"database_id": self.daily_db_id},
                "properties": properties,
            }
            created = self.client.create_page(payload)
            return created["id"]
        except Exception as exc:
            self._log_error("", "create_daily_summary_failed", exc)
            raise
