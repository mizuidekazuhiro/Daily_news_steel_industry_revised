import logging

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
    payload = {}
    total_rows = 0
    skipped_disabled = 0
    skipped_missing_required = 0
    skipped_empty_source = 0
    has_more = True
    start_cursor = None
    while has_more:
        if start_cursor:
            payload["start_cursor"] = start_cursor
        data = notion_client.query_database(database_id, payload)
        for row in data.get("results", []):
            total_rows += 1
            props = row.get("properties", {})
            enabled = props.get("Enabled", {})
            if enabled.get("type") == "checkbox" and not enabled.get("checkbox", False):
                skipped_disabled += 1
                continue

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
            max_pick = None
            max_pick_prop = props.get("MaxPick", {})
            if max_pick_prop.get("type") == "number":
                max_pick = max_pick_prop.get("number")
            if not label or not kind:
                skipped_missing_required += 1
                continue
            if kind == "serper" and not query:
                skipped_empty_source += 1
                continue
            if kind == "rss" and not rss:
                skipped_empty_source += 1
                continue
            results.append({
                "label": label,
                "kind": kind,
                "query": query,
                "rss": rss,
                "enterprise": enterprise,
                "max_pick": max_pick,
            })
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    logging.info(
        "Notion targets loaded: total=%d accepted=%d skipped_disabled=%d skipped_missing_required=%d skipped_empty_source=%d",
        total_rows,
        len(results),
        skipped_disabled,
        skipped_missing_required,
        skipped_empty_source,
    )
    if skipped_missing_required or skipped_empty_source:
        logging.warning(
            "Notion targets skipped due to missing data: missing_required=%d empty_source=%d",
            skipped_missing_required,
            skipped_empty_source,
        )
    return results
