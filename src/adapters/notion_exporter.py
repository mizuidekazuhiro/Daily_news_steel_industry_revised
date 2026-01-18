from src.adapters.notion_audit import write_audit_log
from src.domain.notion_utils import compute_article_id, compute_body_hash, normalize_url, split_text_blocks


class NotionExporter:
    def __init__(self, notion_client, articles_db_id, daily_db_id, run_id, audit_log_path="logs/notion_audit.jsonl"):
        self.client = notion_client
        self.articles_db_id = articles_db_id
        self.daily_db_id = daily_db_id
        self.run_id = run_id
        self.audit_log_path = audit_log_path

    def _log_error(self, url, reason, error):
        write_audit_log(
            {
                "run_id": self.run_id,
                "url": url,
                "reason": reason,
                "error": str(error),
            },
            path=self.audit_log_path,
        )

    def _build_article_properties(self, article, normalized_url, article_id, body_hash):
        label = article.get("label")
        article_type = article.get("type")
        importance = article.get("importance")
        published_source = article.get("published_source", "unknown")
        published_at = article.get("published_at")
        properties = {
            "Name": {"title": [{"text": {"content": article.get("title", "")}}]},
            "URL": {"url": article.get("url", "")},
            "Source": {"rich_text": [{"text": {"content": article.get("source", "")}}]},
            "Label": {"select": {"name": label}} if label else {"select": None},
            "Type": {"select": {"name": article_type}} if article_type else {"select": None},
            "Country": {"multi_select": [{"name": c} for c in article.get("country_tags", [])]},
            "Sector": {"multi_select": [{"name": s} for s in article.get("sector_tags", [])]},
            "Importance": {"select": {"name": importance}} if importance else {"select": None},
            "ImportanceScore": {"number": float(article.get("importance_score", 0))},
            "ImportanceReasons": {"rich_text": [{"text": {"content": article.get("importance_reasons", "")}}]},
            "PublishedAt": {"date": {"start": published_at}} if published_at else {"date": None},
            "PublishedSource": {"select": {"name": published_source}} if published_source else {"select": None},
            "ArticleId": {"rich_text": [{"text": {"content": article_id}}]},
            "NormalizedURL": {"url": normalized_url},
            "BodyHash": {"rich_text": [{"text": {"content": body_hash}}]},
            "Body": {"rich_text": [{"text": {"content": article.get("body", "")}}]},
        }
        return properties

    def _find_article_page(self, article_id):
        payload = {
            "filter": {
                "property": "ArticleId",
                "rich_text": {"equals": article_id},
            }
        }
        data = self.client.query_database(self.articles_db_id, payload)
        results = data.get("results", [])
        return results[0] if results else None

    def _clear_page_blocks(self, page_id):
        start_cursor = None
        while True:
            children = self.client.list_block_children(page_id, start_cursor=start_cursor)
            for block in children.get("results", []):
                self.client.delete_block(block["id"])
            if not children.get("has_more"):
                break
            start_cursor = children.get("next_cursor")

    def _append_body_blocks(self, page_id, body_text):
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
            self.client.append_block_children(page_id, payload)

    def upsert_article(self, article):
        normalized_url = normalize_url(article.get("url", ""))
        article_id = compute_article_id(article.get("url", ""))
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
                body_hash_prop = page.get("properties", {}).get("BodyHash", {})
                if body_hash_prop.get("type") == "rich_text":
                    current_hash = "".join(t.get("plain_text", "") for t in body_hash_prop.get("rich_text", []))
                self.client.update_page(page_id, {"properties": properties})
                if current_hash != body_hash:
                    self._clear_page_blocks(page_id)
                    if body_text:
                        self._append_body_blocks(page_id, body_text)
                return page_id
            payload = {
                "parent": {"database_id": self.articles_db_id},
                "properties": properties,
            }
            created = self.client.create_page(payload)
            page_id = created["id"]
            if body_text:
                self._append_body_blocks(page_id, body_text)
            return page_id
        except Exception as exc:
            self._log_error(article.get("url", ""), "upsert_article_failed", exc)
            raise

    def create_daily_summary(self, run_date, morning_summary, article_page_ids):
        try:
            payload = {
                "parent": {"database_id": self.daily_db_id},
                "properties": {
                    "Name": {"title": [{"text": {"content": f"Daily Summary {run_date}"}}]},
                    "RunId": {"rich_text": [{"text": {"content": self.run_id}}]},
                    "RunDate": {"date": {"start": run_date}},
                    "MorningSummary": {"rich_text": [{"text": {"content": morning_summary}}]},
                    "Articles": {"relation": [{"id": page_id} for page_id in article_page_ids]},
                },
            }
            created = self.client.create_page(payload)
            return created["id"]
        except Exception as exc:
            self._log_error("", "create_daily_summary_failed", exc)
            raise
