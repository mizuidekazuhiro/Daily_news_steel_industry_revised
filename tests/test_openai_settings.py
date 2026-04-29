from src.adapters import openai_summarizer
from src.config.settings import load_settings


def test_settings_contains_openai_models():
    s = load_settings()
    assert s["openai"]["label_summary"]["model"] == "gpt-4o-mini"
    assert s["openai"]["morning_summary"]["model"] == "gpt-5-mini"


def test_summarize_with_gpt_uses_passed_settings(monkeypatch):
    captured = {}

    def fake_call_openai(**kwargs):
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr(openai_summarizer, "_call_openai", fake_call_openai)
    html = openai_summarizer.summarize_with_gpt(
        "L",
        [{"type": "BUS", "date": "2026-01-01", "title": "t", "body": "b"}],
        [{"date": "2026-01-01", "url": "u", "title": "t", "source": "s"}],
        "sys",
        {"model": "gpt-4o-mini", "reasoning_effort": "low", "verbosity": "low", "max_output_tokens": 1000},
    )
    assert "■L" in html
    assert captured["model"] == "gpt-4o-mini"


def test_generate_morning_summary_uses_passed_settings_and_header(monkeypatch):
    captured = {}

    def fake_call_openai(**kwargs):
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr(openai_summarizer, "_call_openai", fake_call_openai)
    html = openai_summarizer.generate_morning_summary([], "prompt", {"model": "gpt-5-mini"})
    assert "■ 本日の事業ブリーフ" in html
    assert captured["model"] == "gpt-5-mini"


def test_stock_type_is_excluded_from_morning_prompt(monkeypatch):
    captured = {}

    def fake_call_openai(**kwargs):
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr(openai_summarizer, "_call_openai", fake_call_openai)
    openai_summarizer.generate_morning_summary(
        [{"type": "STOCK", "title": "a"}, {"type": "stock", "title": "b"}, {"type": "NEWS", "title": "c", "body": "x"}],
        "prompt",
        {"model": "gpt-5-mini"},
    )
    assert "タイトル: c" in captured["prompt"]
    assert "タイトル: a" not in captured["prompt"]
    assert "タイトル: b" not in captured["prompt"]
