def _property_text(prop):
    if not prop:
        return ""
    if prop.get("type") == "title":
        return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    if prop.get("type") == "rich_text":
        return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
    return ""


def _property_select(prop):
    if prop and prop.get("type") == "select":
        return (prop.get("select") or {}).get("name") or ""
    return ""


def _property_number(prop):
    if prop and prop.get("type") == "number":
        return prop.get("number")
    return None


def _property_checkbox(prop):
    if prop and prop.get("type") == "checkbox":
        return prop.get("checkbox", False)
    return False


def fetch_rules_from_notion(notion_client, database_id):
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
            rule_type = _property_select(props.get("RuleType"))
            tag_name = _property_text(props.get("TagName"))
            keywords = _property_text(props.get("Keywords"))
            negative = _property_text(props.get("NegativeKeywords"))
            match_field = _property_select(props.get("MatchField")) or "both"
            weight = _property_number(props.get("Weight"))
            priority = _property_number(props.get("Priority"))
            notes = _property_text(props.get("Notes"))
            if not rule_type or not tag_name:
                continue
            results.append({
                "rule_type": rule_type.lower(),
                "tag_name": tag_name,
                "keywords": keywords,
                "negative_keywords": negative,
                "match_field": match_field.lower(),
                "weight": weight,
                "priority": priority,
                "notes": notes,
            })
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    return results
