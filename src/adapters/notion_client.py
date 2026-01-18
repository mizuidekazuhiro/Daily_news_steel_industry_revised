import random
import time
import requests


class NotionClient:
    def __init__(self, token, audit_logger=None, max_retries=5, base_url="https://api.notion.com/v1"):
        self.token = token
        self.base_url = base_url
        self.max_retries = max_retries
        self.audit_logger = audit_logger

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

    def _request(self, method, path, json_body=None, params=None):
        url = f"{self.base_url}{path}"
        for attempt in range(self.max_retries):
            response = requests.request(
                method,
                url,
                headers=self._headers(),
                json=json_body,
                params=params,
                timeout=30,
            )
            if response.status_code == 429 or response.status_code >= 500:
                retry_after = response.headers.get("Retry-After")
                base_sleep = float(retry_after) if retry_after else min(2 ** attempt, 30)
                jitter = random.uniform(0, 1)
                time.sleep(base_sleep + jitter)
                continue
            if response.status_code >= 400:
                raise requests.HTTPError(
                    f"Notion API error {response.status_code}: {response.text}",
                    response=response,
                )
            return response.json()
        raise requests.HTTPError(f"Notion API rate limit exceeded for {url}")

    def query_database(self, database_id, payload):
        return self._request("POST", f"/databases/{database_id}/query", json_body=payload)

    def create_page(self, payload):
        return self._request("POST", "/pages", json_body=payload)

    def update_page(self, page_id, payload):
        return self._request("PATCH", f"/pages/{page_id}", json_body=payload)

    def list_block_children(self, block_id, start_cursor=None, page_size=100):
        params = {"page_size": page_size}
        if start_cursor:
            params["start_cursor"] = start_cursor
        return self._request("GET", f"/blocks/{block_id}/children", params=params)

    def append_block_children(self, block_id, payload):
        return self._request("PATCH", f"/blocks/{block_id}/children", json_body=payload)

    def delete_block(self, block_id):
        return self._request("DELETE", f"/blocks/{block_id}")
