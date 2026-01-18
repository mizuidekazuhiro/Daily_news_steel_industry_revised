from src.adapters.notion_client import NotionClient


def _property_text(prop):
    if not prop:
        return ""
    if prop.get("type") == "title":
        return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    if prop.get("type") == "rich_text":
        return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
    if prop.get("type") == "url":
        return prop.get("url") or ""
    return ""


def fetch_targets_from_notion(notion_client, database_id):
    results = []
    payload = {
        "filter": {"property": "Enabled", "checkbox": {"equals": True}},
    }
    has_more = True
    start_cursor = None
    while has_more:
        if start_cursor:
            payload["start_cursor"] = start_cursor
        data = notion_client.query_database(database_id, payload)
        for row in data.get("results", []):
            props = row.get("properties", {})
            label = _property_text(props.get("Label"))
            kind_prop = props.get("Kind", {})
            kind = None
            if kind_prop.get("type") == "select":
                kind = (kind_prop.get("select") or {}).get("name")
            query = _property_text(props.get("Query"))
            rss = _property_text(props.get("RSS"))
            enterprise = False
            if props.get("Enterprise", {}).get("type") == "checkbox":
                enterprise = props.get("Enterprise", {}).get("checkbox", False)
            if not label or not kind:
                continue
            results.append({
                "label": label,
                "kind": kind,
                "query": query,
                "rss": rss,
                "enterprise": enterprise,
            })
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    return results
