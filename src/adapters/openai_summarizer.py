import html
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)




def normalize_morning_summary_text(text):
    raw = str(text or "").replace("\r\n", "\n").strip()
    lines = [line.rstrip() for line in raw.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and re.sub(r"\s+", "", lines[0]).startswith("■本日の事業ブリーフ"):
        lines.pop(0)
    return "\n".join(lines).strip()


def _render_label_item(line):
    escaped = html.escape(line.strip())
    for key in ("事実：", "示唆：", "見るべき点："):
        prefix = f"- {key}"
        if line.strip().startswith(prefix):
            body = html.escape(line.strip()[len(prefix):].strip())
            return f'<li style="margin:6px 0;"><strong>{html.escape(key)}</strong> {body}</li>'
    return f'<li style="margin:6px 0;">{escaped}</li>'


def render_morning_summary_html(summary_text):
    section_titles = ["結論", "重要トピック", "商社目線の読み", "今日の確認ポイント", "根拠記事"]
    section_pattern = re.compile(r"^【(" + "|".join(map(re.escape, section_titles)) + r")】\s*$")
    topic_pattern = re.compile(r"^(\d+)\.\s*(.+)$")

    lines = [line.strip() for line in str(summary_text or "").split("\n")]
    parts = []
    current_section = None
    in_list = False
    in_topic = False

    def close_lists():
        nonlocal in_list, in_topic
        if in_list:
            parts.append("</ul>")
            in_list = False
        if in_topic:
            parts.append("</div>")
            in_topic = False

    for raw in lines:
        if not raw:
            continue
        section_match = section_pattern.match(raw)
        topic_match = topic_pattern.match(raw)

        if section_match:
            close_lists()
            title = section_match.group(1)
            parts.append(f'<h3 style="margin:16px 0 8px; font-size:17px; color:#1f2937;">【{html.escape(title)}】</h3>')
            current_section = title
            continue

        if topic_match and current_section == "重要トピック":
            close_lists()
            num, title = topic_match.groups()
            parts.append('<div style="background:#ffffff; border:1px solid #e5e7eb; border-radius:8px; padding:12px 14px; margin-bottom:12px;">')
            parts.append(f'<div style="font-weight:700; margin-bottom:6px;">{html.escape(num)}. {html.escape(title)}</div>')
            parts.append('<ul style="margin:0; padding-left:18px;">')
            in_list = True
            in_topic = True
            continue

        if raw.startswith("-"):
            if not in_list:
                parts.append('<ul style="margin:6px 0 10px; padding-left:18px;">')
                in_list = True
            parts.append(_render_label_item(raw))
            continue

        close_lists()
        parts.append(f'<p style="margin:6px 0;">{html.escape(raw)}</p>')

    close_lists()
    return (
        '<div style="font-family:-apple-system, BlinkMacSystemFont, &quot;Yu Gothic&quot;, &quot;Meiryo&quot;, &quot;Meiryo UI&quot;, sans-serif; '
        'max-width:760px; margin:0 auto; line-height:1.75; color:#1f2937; background:#f7f8fa; border:1px solid #e5e7eb; padding:16px;">'
        '<h2 style="margin:0 0 12px; font-size:22px;">■ 本日の事業ブリーフ</h2>'
        + ''.join(parts)
        + '</div>'
    )
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


def _extract_responses_text(data):
    if data.get("output_text"):
        return data["output_text"]
    for out in data.get("output", []):
        for content in out.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return content["text"]
    return None


def _call_openai_responses(input_text, model="gpt-5-mini", reasoning_effort="medium", verbosity="medium", max_output_tokens=2200, timeout=180, prompt_chars=None):
    api_key = _get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is empty")
    retry = 0
    current_max_output_tokens = max_output_tokens
    while retry <= 1:
        res = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "input": input_text,
                "reasoning": {"effort": reasoning_effort},
                "text": {"verbosity": verbosity},
                "max_output_tokens": current_max_output_tokens,
            },
            timeout=timeout,
        )
        if res.status_code >= 400:
            logger.error("OpenAI API failed: api=responses status=%s model=%s body=%s", res.status_code, model, res.text[:2000])
        res.raise_for_status()
        data = res.json()
        usage = _extract_usage(data)
        logger.info("OpenAI API success: api=responses usage=%s", usage)
        if usage and current_max_output_tokens:
            output_tokens = int(usage.get("output_tokens") or 0)
            reasoning_tokens = int(usage.get("reasoning_tokens") or 0)
            if output_tokens >= int(current_max_output_tokens * 0.95):
                logger.warning(
                    "OpenAI Responses output near max_output_tokens: model=%s output_tokens=%d reasoning_tokens=%d max_output_tokens=%d prompt_chars=%s",
                    model,
                    output_tokens,
                    reasoning_tokens,
                    current_max_output_tokens,
                    prompt_chars,
                )
        output_text = _extract_responses_text(data) or ""
        if data.get("status") == "incomplete" or data.get("incomplete_details"):
            logger.error(
                "OpenAI responses incomplete: model=%s incomplete_details=%s usage=%s output_head=%s",
                model,
                data.get("incomplete_details"),
                usage,
                output_text[:400],
            )
            retry += 1
            if retry > 1:
                raise RuntimeError("Morning summary generation failed due to incomplete response")
            current_max_output_tokens = min(current_max_output_tokens * 2, 6000)
            continue
        if output_text:
            return output_text
        raise RuntimeError("Responses API output text not found")
    raise RuntimeError("Responses API request failed")


def _call_openai(*, model, prompt, system_prompt=None, temperature=0.2, reasoning_effort="low", verbosity="low", max_output_tokens=1200, timeout=120):
    if _is_gpt5_model(model):
        input_text = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        return _call_openai_responses(input_text=input_text, model=model, reasoning_effort=reasoning_effort, verbosity=verbosity, max_output_tokens=max_output_tokens, timeout=timeout, prompt_chars=len(input_text))
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
        summary_text = _call_openai(
            model=model,
            prompt=prompt,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity,
            max_output_tokens=max_output_tokens,
            timeout=timeout,
        )
        normalized = normalize_morning_summary_text(summary_text)
        return render_morning_summary_html(normalized)
    except Exception as e:
        logger.exception("generate_morning_summary failed: prompt_chars=%d", len(prompt))
        return f"<b>■本日の事業ブリーフ</b><br>生成できませんでした（{type(e).__name__}）<br><br>"
