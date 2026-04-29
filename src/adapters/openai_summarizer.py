import logging
import os

import requests

logger = logging.getLogger(__name__)


def _get_openai_api_key():
    return os.environ.get("OPENAI_API_KEY", "")


def _is_gpt5_model(model):
    return str(model or "").startswith("gpt-5")


def _extract_usage(data):
    usage = data.get("usage")
    return usage if isinstance(usage, dict) else None


def _call_openai_chat(messages, model="gpt-4o-mini", temperature=0.2, timeout=120):
    api_key = _get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is empty")
    res = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": temperature},
        timeout=timeout,
    )
    if res.status_code >= 400:
        logger.error("OpenAI API failed: api=chat status=%s model=%s body=%s", res.status_code, model, res.text[:2000])
    res.raise_for_status()
    data = res.json()
    logger.info("OpenAI API success: api=chat usage=%s", _extract_usage(data))
    return data["choices"][0]["message"]["content"]


def _call_openai_responses(input_text, model="gpt-5-mini", reasoning_effort="medium", verbosity="medium", max_output_tokens=2200, timeout=180):
    api_key = _get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is empty")
    res = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "input": input_text,
            "reasoning": {"effort": reasoning_effort},
            "text": {"verbosity": verbosity},
            "max_output_tokens": max_output_tokens,
        },
        timeout=timeout,
    )
    if res.status_code >= 400:
        logger.error("OpenAI API failed: api=responses status=%s model=%s body=%s", res.status_code, model, res.text[:2000])
    res.raise_for_status()
    data = res.json()
    logger.info("OpenAI API success: api=responses usage=%s", _extract_usage(data))
    if data.get("output_text"):
        return data["output_text"]
    for out in data.get("output", []):
        for content in out.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return content["text"]
    raise RuntimeError("Responses API output text not found")


def _call_openai(*, model, prompt, system_prompt=None, temperature=0.2, reasoning_effort="low", verbosity="low", max_output_tokens=1200, timeout=120):
    if _is_gpt5_model(model):
        input_text = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        return _call_openai_responses(input_text=input_text, model=model, reasoning_effort=reasoning_effort, verbosity=verbosity, max_output_tokens=max_output_tokens, timeout=timeout)
    messages = [{"role": "user", "content": prompt}]
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
    return _call_openai_chat(messages=messages, model=model, temperature=temperature, timeout=timeout)


def _article_value(article, *keys, default=""):
    for key in keys:
        value = article.get(key)
        if value not in (None, "", []):
            return value
    return default


def summarize_with_gpt(label, summary_articles, display_articles, system_prompt, openai_settings=None):
    conf = openai_settings or {}
    model = conf.get("model", "gpt-4o-mini")
    temperature = float(conf.get("temperature", 0.2))
    reasoning_effort = conf.get("reasoning_effort", "low")
    verbosity = conf.get("verbosity", "low")
    max_output_tokens = int(conf.get("max_output_tokens", 1200))
    timeout = int(conf.get("timeout", 120))

    prompt = ""
    for a in summary_articles:
        prompt += f"\n区分: {a.get('type')}\n公開日: {a.get('date')}\nタイトル: {a.get('title')}\n本文:\n{a.get('body')}\n\n"
    try:
        if not summary_articles:
            body = "要約対象なし（importance <= 0）"
        else:
            logger.info("summarize_with_gpt: label=%s model=%s prompt_chars=%d input article count=%d reasoning_effort=%s verbosity=%s max_output_tokens=%d", label, model, len(prompt), len(summary_articles), reasoning_effort, verbosity, max_output_tokens)
            body = _call_openai(model=model, prompt=prompt, system_prompt=system_prompt, temperature=temperature, reasoning_effort=reasoning_effort, verbosity=verbosity, max_output_tokens=max_output_tokens, timeout=timeout).replace("\n", "<br>")
        out = f"""<div style=\"font-family:'Meiryo UI', sans-serif; line-height:1.7; padding:22px; color:#333; border-bottom:1px solid #ddd;\">\n            <h2 style=\"color:#0055a5; margin-bottom:10px;\">■{label}</h2>\n            <div style=\"margin-bottom:14px;\">{body}</div>\n        """
        for i, a in enumerate(display_articles, 1):
            date_only = a["date"].split(" ")[0] if a.get("date") else "不明"
            out += f"""\n            <div style=\"margin-bottom:8px;\">\n                <strong>{i}.</strong> <a href=\"{a['url']}\">{a['title']}</a><br>\n                <span style=\"font-size:12px; color:#666;\">Published: {date_only} | Source: {a['source']}</span>\n            </div>\n            """
        return out + "</div><br>"
    except Exception as e:
        logger.exception("summarize_with_gpt failed: label=%s prompt_chars=%d", label, len(prompt))
        return f"<b> ■{label}</b><br>GPTエラー（{type(e).__name__}）<br><br>"


def generate_morning_summary(all_articles, user_prompt, openai_settings=None):
    conf = openai_settings or {}
    model = conf.get("model", "gpt-5-mini")
    temperature = float(conf.get("temperature", 0.2))
    reasoning_effort = conf.get("reasoning_effort", "medium")
    verbosity = conf.get("verbosity", "medium")
    max_output_tokens = int(conf.get("max_output_tokens", 2200))
    timeout = int(conf.get("timeout", 180))
    prompt = user_prompt + "\n"
    try:
        items = []
        if isinstance(all_articles, dict):
            for label, articles in all_articles.items():
                for article in articles:
                    copied = dict(article)
                    copied.setdefault("label", label)
                    items.append(copied)
        else:
            items = list(all_articles or [])

        prompt_count = 0
        for article in items:
            if str(article.get("type", "")).lower() == "stock":
                continue
            prompt_count += 1
            label = _article_value(article, "label", "target_label")
            prompt += f"""
会社/テーマ: {label}
区分: {_article_value(article, 'type')}
重要度スコア: {_article_value(article, 'importance_score', 'score')}
重要度理由: {_article_value(article, 'importance_reasons', 'importance_reason')}
国タグ: {_article_value(article, 'country', 'countries')}
主国: {_article_value(article, 'primary_country', 'PrimaryCountry')}
分野タグ: {_article_value(article, 'sector', 'sectors')}
公開日: {_article_value(article, 'date')}
Source: {_article_value(article, 'source')}
URL: {_article_value(article, 'url')}
タイトル: {_article_value(article, 'title')}
本文抜粋:
{_article_value(article, 'body', 'body_preview')}

"""
        logger.info("generate_morning_summary: model=%s prompt_chars=%d input article count=%d prompt article count=%d reasoning_effort=%s verbosity=%s max_output_tokens=%d timeout=%d", model, len(prompt), len(items), prompt_count, reasoning_effort, verbosity, max_output_tokens, timeout)
        summary = _call_openai(model=model, prompt=prompt, temperature=temperature, reasoning_effort=reasoning_effort, verbosity=verbosity, max_output_tokens=max_output_tokens, timeout=timeout).replace("\n", "<br>")
        return f"""
        <div style="font-family:'Meiryo UI', sans-serif; padding:20px; background:#f5f7fa; border:1px solid #ddd; margin-bottom:24px; color:#333;">
            <h2 style="margin-top:0;">■ 本日の事業ブリーフ</h2>
            <div style="line-height:1.7;">{summary}</div>
        </div>
        """
    except Exception as e:
        logger.exception("generate_morning_summary failed: prompt_chars=%d", len(prompt))
        return f"<b>■本日の事業ブリーフ</b><br>生成できませんでした（{type(e).__name__}）<br><br>"
