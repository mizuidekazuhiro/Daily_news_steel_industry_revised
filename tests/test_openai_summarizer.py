from src.adapters import openai_summarizer


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self._payload


def test_gpt5_model_uses_responses_endpoint(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    called = {}

    def fake_post(url, headers, json, timeout):
        called["url"] = url
        return DummyResponse({"output_text": "ok", "usage": {"total_tokens": 10}})

    monkeypatch.setattr(openai_summarizer.requests, "post", fake_post)

    out = openai_summarizer._call_openai(
        model="gpt-5.4-mini",
        prompt="hello",
        reasoning_effort="medium",
        verbosity="medium",
        max_output_tokens=100,
    )

    assert out == "ok"
    assert called["url"] == "https://api.openai.com/v1/responses"


def test_non_gpt5_model_uses_chat_completions_endpoint(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    called = {}

    def fake_post(url, headers, json, timeout):
        called["url"] = url
        return DummyResponse({"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 10}})

    monkeypatch.setattr(openai_summarizer.requests, "post", fake_post)

    out = openai_summarizer._call_openai(
        model="gpt-4o-mini",
        prompt="hello",
        temperature=0.2,
    )

    assert out == "ok"
    assert called["url"] == "https://api.openai.com/v1/chat/completions"


def test_morning_summary_default_model_is_gpt5mini(monkeypatch):
    monkeypatch.delenv("OPENAI_MORNING_SUMMARY_MODEL", raising=False)
    captured = {}

    def fake_call_openai(**kwargs):
        captured["model"] = kwargs["model"]
        return "summary"

    monkeypatch.setattr(openai_summarizer, "_call_openai", fake_call_openai)

    html = openai_summarizer.generate_morning_summary([], "prompt")

    assert "本日の事業ブリーフ" in html
    assert captured["model"] == "gpt-5-mini"


def test_label_summary_default_model_is_gpt4omini(monkeypatch):
    monkeypatch.delenv("OPENAI_LABEL_SUMMARY_MODEL", raising=False)
    captured = {}

    def fake_call_openai(**kwargs):
        captured["model"] = kwargs["model"]
        return "summary"

    monkeypatch.setattr(openai_summarizer, "_call_openai", fake_call_openai)

    html = openai_summarizer.summarize_with_gpt(
        "label",
        [{"type": "BUSINESS", "date": "2026-01-01", "title": "t", "body": "b"}],
        [{"date": "2026-01-01", "url": "https://example.com", "title": "t", "source": "src"}],
        "system",
    )

    assert "■label" in html
    assert captured["model"] == "gpt-4o-mini"


def test_responses_api_extracts_output_text(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_post(url, headers, json, timeout):
        return DummyResponse({"output_text": "from_output_text", "usage": {"total_tokens": 10}})

    monkeypatch.setattr(openai_summarizer.requests, "post", fake_post)

    out = openai_summarizer._call_openai_responses(input_text="x")

    assert out == "from_output_text"


def test_responses_api_extracts_output_content_output_text(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_post(url, headers, json, timeout):
        return DummyResponse(
            {
                "output": [
                    {"content": [{"type": "output_text", "text": "from_output_content"}]},
                ],
                "usage": {"total_tokens": 10},
            }
        )

    monkeypatch.setattr(openai_summarizer.requests, "post", fake_post)

    out = openai_summarizer._call_openai_responses(input_text="x")

    assert out == "from_output_content"
