from src.adapters.notion_targets import _split_serper_queries, fetch_targets_from_notion
from src.adapters.targets_yaml import _merge_notion_targets


class StubNotionClient:
    def __init__(self, results):
        self._results = results

    def query_database(self, database_id, payload):
        return {
            "results": self._results,
            "has_more": False,
            "next_cursor": None,
        }


def _notion_row(query_text):
    return {
        "properties": {
            "Enabled": {"type": "checkbox", "checkbox": True},
            "Label": {"type": "title", "title": [{"plain_text": "日本製鉄"}]},
            "Kind": {"type": "select", "select": {"name": "serper"}},
            "Query": {"type": "rich_text", "rich_text": [{"plain_text": query_text}]},
            "RSS": {"type": "url", "url": None},
            "Enterprise": {"type": "checkbox", "checkbox": False},
            "MaxPick": {"type": "number", "number": None},
        }
    }


def test_split_serper_queries_single_line():
    assert _split_serper_queries("日本製鉄") == ["日本製鉄"]


def test_split_serper_queries_multi_line():
    assert _split_serper_queries('日本製鉄\n"Nippon Steel"') == ["日本製鉄", '"Nippon Steel"']


def test_split_serper_queries_ignores_empty_lines():
    assert _split_serper_queries('日本製鉄\n\n"Nippon Steel"\n') == ["日本製鉄", '"Nippon Steel"']


def test_split_serper_queries_trims_whitespace_and_crlf():
    assert _split_serper_queries('  日本製鉄  \r\n  "Nippon Steel"  ') == ["日本製鉄", '"Nippon Steel"']


def test_split_serper_queries_empty_text():
    assert _split_serper_queries("") == []


def test_fetch_targets_from_notion_skips_empty_query_after_split():
    notion_client = StubNotionClient([_notion_row("\n  \n")])

    result = fetch_targets_from_notion(notion_client, "dummy")

    assert result == []


def test_merge_notion_targets_extends_queries_for_same_label(monkeypatch):
    monkeypatch.setattr("src.adapters.targets_yaml.env.NOTION_TOKEN", "token")
    monkeypatch.setattr("src.adapters.targets_yaml.env.NOTION_TARGETS_DB_ID", "db")
    monkeypatch.setattr("src.adapters.targets_yaml.NotionClient", lambda token: object())
    monkeypatch.setattr(
        "src.adapters.targets_yaml.fetch_targets_from_notion",
        lambda client, db_id: [
            {
                "label": "日本製鉄",
                "kind": "serper",
                "query": '日本製鉄\n"Nippon Steel"',
                "queries": ["日本製鉄", '"Nippon Steel"'],
                "rss": "",
                "enterprise": False,
                "max_pick": None,
            }
        ],
    )

    targets, _, _, _ = _merge_notion_targets({}, set(), {}, {})

    assert targets == {"日本製鉄": ["日本製鉄", '"Nippon Steel"']}
