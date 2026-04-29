import os
import logging
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
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
        },
        timeout=timeout,
    )

    # 失敗時に内容が分かるようにする
    if res.status_code >= 400:
        logger.error("OpenAI API error: status=%s body=%s", res.status_code, res.text[:2000])

    res.raise_for_status()
    data = res.json()
    logger.info("OpenAI usage(chat): %s", _extract_usage(data))
    return data["choices"][0]["message"]["content"]


def _call_openai_responses(
    input_text,
    model="gpt-5.4-mini",
    reasoning_effort="medium",
    verbosity="medium",
    max_output_tokens=2200,
    timeout=120,
):
    api_key = _get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is empty")

    res = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
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
        logger.error("OpenAI API error: status=%s body=%s", res.status_code, res.text[:2000])

    res.raise_for_status()
    data = res.json()
    logger.info("OpenAI usage(responses): %s", _extract_usage(data))

    output_text = data.get("output_text")
    if output_text:
        return output_text

    for output_item in data.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text" and content_item.get("text"):
                return content_item["text"]

    raise RuntimeError("Responses API output text not found")


def _call_openai(
    *,
    model,
    prompt,
    system_prompt=None,
    temperature=0.2,
    reasoning_effort="low",
    verbosity="low",
    max_output_tokens=1200,
    timeout=120,
):
    if _is_gpt5_model(model):
        logger.info(
            "Using responses API for GPT-5 model: model=%s reasoning_effort=%s verbosity=%s",
            model,
            reasoning_effort,
            verbosity,
        )
        input_text = prompt
        if system_prompt:
            input_text = f"{system_prompt}\n\n{prompt}"
        return _call_openai_responses(
            input_text=input_text,
            model=model,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity,
            max_output_tokens=max_output_tokens,
            timeout=timeout,
        )

    messages = [{"role": "user", "content": prompt}]
    if system_prompt:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
    return _call_openai_chat(
        messages=messages,
        model=model,
        temperature=temperature,
        timeout=timeout,
    )

def summarize_with_gpt(label, summary_articles, display_articles, system_prompt):
    model = os.environ.get("OPENAI_LABEL_SUMMARY_MODEL", "gpt-4o-mini")
    temperature = float(os.environ.get("OPENAI_LABEL_SUMMARY_TEMPERATURE", "0.2"))
    reasoning_effort = os.environ.get("OPENAI_LABEL_SUMMARY_REASONING_EFFORT", "low")
    verbosity = os.environ.get("OPENAI_LABEL_SUMMARY_VERBOSITY", "low")
    max_output_tokens = int(os.environ.get("OPENAI_LABEL_SUMMARY_MAX_OUTPUT_TOKENS", "1200"))

    prompt = ""
    for a in summary_articles:
        prompt += f"""
区分: {a.get("type")}
公開日: {a.get("date")}
タイトル: {a.get("title")}
本文:
{a.get("body")}

"""

    try:
        if not summary_articles:
            body = "要約対象なし（importance <= 0）"
        else:
            logger.info(
                "summarize_with_gpt: label=%s prompt_chars=%d input article count=%d label summary model=%s reasoning_effort=%s verbosity=%s",
                label,
                len(prompt),
                len(summary_articles),
                model,
                reasoning_effort,
                verbosity,
            )

            body = _call_openai(
                model=model,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
                verbosity=verbosity,
                max_output_tokens=max_output_tokens,
                timeout=120,
            ).replace("\n", "<br>")

        # ... out の組み立てはそのまま ...
        out = f"""<div style="font-family:'Meiryo UI', sans-serif; line-height:1.7; padding:22px; color:#333; border-bottom:1px solid #ddd;">
            <h2 style="color:#0055a5; margin-bottom:10px;">■{label}</h2>
            <div style="margin-bottom:14px;">{body}</div>
        """
        for i, a in enumerate(display_articles, 1):
            date_only = a["date"].split(" ")[0] if a.get("date") else "不明"
            out += f"""
            <div style="margin-bottom:8px;">
                <strong>{i}.</strong> <a href="{a["url"]}">{a["title"]}</a><br>
                <span style="font-size:12px; color:#666;">Published: {date_only} | Source: {a["source"]}</span>
            </div>
            """
        out += "</div><br>"
        return out

    except Exception as e:
        logger.exception("summarize_with_gpt failed: label=%s prompt_chars=%d", label, len(prompt))
        return f"<b> ■{label}</b><br>GPTエラー（{type(e).__name__}）<br><br>"

def generate_morning_summary(all_articles, user_prompt):
    try:
        model = os.environ.get("OPENAI_MORNING_SUMMARY_MODEL", "gpt-5.4-mini")
        temperature = float(os.environ.get("OPENAI_MORNING_SUMMARY_TEMPERATURE", "0.2"))
        reasoning_effort = os.environ.get("OPENAI_MORNING_SUMMARY_REASONING_EFFORT", "medium")
        verbosity = os.environ.get("OPENAI_MORNING_SUMMARY_VERBOSITY", "medium")
        max_output_tokens = int(os.environ.get("OPENAI_MORNING_SUMMARY_MAX_OUTPUT_TOKENS", "2200"))
        prompt = user_prompt + "\n"

        if isinstance(all_articles, dict):
            items = []
            for label, articles in all_articles.items():
                for article in articles:
                    copied = dict(article)
                    copied.setdefault("label", label)
                    items.append(copied)
        else:
            items = list(all_articles or [])

        for article in items:
            if article.get("type") == "STOCK":
                continue
            label = article.get("label") or article.get("target_label", "")
            prompt += f"""
会社/テーマ: {label}
区分: {article.get("type")}
重要度スコア: {article.get("importance_score")}
重要度理由: {article.get("importance_reasons")}
国タグ: {article.get("country")}
主国: {article.get("primary_country")}
分野タグ: {article.get("sector")}
公開日: {article.get("date")}
Source: {article.get("source")}
URL: {article.get("url")}
タイトル: {article.get("title")}
本文:
{article.get("body")}

"""

        logger.info(
            "generate_morning_summary: prompt_chars=%d input article count=%d morning summary model=%s reasoning_effort=%s verbosity=%s",
            len(prompt),
            len(items),
            model,
            reasoning_effort,
            verbosity,
        )

        summary = _call_openai(
            model=model,
            prompt=prompt,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity,
            max_output_tokens=max_output_tokens,
            timeout=120,
        ).replace("\n", "<br>")

        return f"""
        <div style="font-family:'Meiryo UI', sans-serif; padding:20px; background:#f5f7fa; border:1px solid #ddd; margin-bottom:24px; color:#333;">
            <h2 style="margin-top:0;">■ 本日のニュースサマリ</h2>
            <div style="line-height:1.7;">{summary}</div>
        </div>
        """

    except Exception as e:
        logger.exception("generate_morning_summary failed: prompt_chars=%d", len(prompt) if 'prompt' in locals() else -1)
        return f"<b>■本日のニュースサマリ</b><br>生成できませんでした（{type(e).__name__}）<br><br>"
