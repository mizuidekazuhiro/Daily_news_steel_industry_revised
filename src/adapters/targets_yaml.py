from src.config.yaml_loader import load_yaml
from src.config import env
from src.adapters.notion_client import NotionClient
from src.adapters.notion_targets import fetch_targets_from_notion


def _merge_notion_targets(targets, enterprise_targets, google_alert_rss):
    if not (env.NOTION_TOKEN and env.NOTION_TARGETS_DB_ID):
        return targets, enterprise_targets, google_alert_rss

    client = NotionClient(env.NOTION_TOKEN)
    notion_targets = fetch_targets_from_notion(client, env.NOTION_TARGETS_DB_ID)
    for entry in notion_targets:
        label = entry["label"]
        kind = entry["kind"]
        if kind == "serper" and entry.get("query"):
            targets.setdefault(label, []).append(entry["query"])
        if kind == "rss" and entry.get("rss"):
            google_alert_rss.setdefault(label, []).append(entry["rss"])
        if entry.get("enterprise"):
            enterprise_targets.add(label)
    return targets, enterprise_targets, google_alert_rss


def load_targets(path="config/targets.yml"):
    data = load_yaml(path)
    targets = data.get("targets", {})
    enterprise_targets = set(data.get("enterprise_targets", []))
    google_alert_rss = data.get("google_alert_rss", {})
    return _merge_notion_targets(targets, enterprise_targets, google_alert_rss)
