from src.config.yaml_loader import load_yaml


def load_targets(path="config/targets.yml"):
    data = load_yaml(path)
    targets = data.get("targets", {})
    enterprise_targets = set(data.get("enterprise_targets", []))
    google_alert_rss = data.get("google_alert_rss", {})
    return targets, enterprise_targets, google_alert_rss
