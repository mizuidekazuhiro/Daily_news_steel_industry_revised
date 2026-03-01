import logging
import requests

logger = logging.getLogger(__name__)

def _call_openai_chat(messages, model="gpt-4o-mini", temperature=0.2, timeout=120):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is empty")

    res = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
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
    return data["choices"][0]["message"]["content"]

def summarize_with_gpt(label, summary_articles, display_articles, system_prompt):
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
            logger.info("summarize_with_gpt: label=%s prompt_chars=%d articles=%d",
                        label, len(prompt), len(summary_articles))

            body = _call_openai_chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                model="gpt-4o-mini",
                temperature=0.2,
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
タイトル: {article.get("title")}
本文:
{article.get("body")}

"""

        logger.info("generate_morning_summary: prompt_chars=%d items=%d", len(prompt), len(items))

        summary = _call_openai_chat(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o-mini",
            temperature=0.3,
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