import json
import os
from datetime import datetime, timezone


def write_audit_log(record, path="logs/notion_audit.jsonl"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **record,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
