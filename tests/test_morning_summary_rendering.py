import pytest

from src.adapters import openai_summarizer


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


def test_normalize_removes_duplicate_header():
    text = "■ 本日の事業ブリーフ\n【結論】\nA"
    normalized = openai_summarizer.normalize_morning_summary_text(text)
    html = openai_summarizer.render_morning_summary_html(normalized)
    assert html.count("■ 本日の事業ブリーフ") == 1


def test_render_structures_sections_topics_and_labels():
    summary = """【結論】
需要は底堅い。
【重要トピック】
1. 高炉再編
- 事実：再編発表
- 示唆：供給最適化
- 見るべき点：価格
"""
    html = openai_summarizer.render_morning_summary_html(summary)
    assert "<h3" in html and "【結論】" in html
    assert "高炉再編" in html and "border:1px solid" in html
    assert "<strong>事実：</strong>" in html
    assert "<strong>示唆：</strong>" in html
    assert "<strong>見るべき点：</strong>" in html


def test_render_escapes_html_chars():
    html = openai_summarizer.render_morning_summary_html("1. <b>x</b>\n- 事実：a < b")
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert "a &lt; b" in html


def test_sanitize_bullet_text():
    assert openai_summarizer.sanitize_bullet_text("・ - 日本向け原油") == "日本向け原油"
    assert openai_summarizer.sanitize_bullet_text("• - Oil tankers") == "Oil tankers"
    assert openai_summarizer.sanitize_bullet_text("- ・ 韓国・台湾") == "韓国・台湾"


def test_evidence_articles_are_linked():
    summary = "【根拠記事】\n- Oil rises"
    html = openai_summarizer.render_morning_summary_html(
        summary,
        source_articles=[{"title": "Oil rises", "url": "https://example.com/a", "source": "Reuters"}],
    )
    assert '<a href="https://example.com/a">Oil rises</a>（Reuters）' in html


def test_call_openai_responses_raises_on_incomplete(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls = {"n": 0}

    def fake_post(url, headers, json, timeout):
        calls["n"] += 1
        return DummyResponse({
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output_text": "truncated",
            "usage": {"total_tokens": 100},
        })

    monkeypatch.setattr(openai_summarizer.requests, "post", fake_post)

    with pytest.raises(RuntimeError):
        openai_summarizer._call_openai_responses(input_text="x", max_output_tokens=100)
    assert calls["n"] == 2
