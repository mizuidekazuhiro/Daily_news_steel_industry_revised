import requests

from src.config.env import OPENAI_API_KEY


def summarize_with_gpt(label, articles, system_prompt):
    try:
        prompt = ""
        for a in articles:
            prompt += f"""
区分: {a.get("type")}
公開日: {a.get("date")}
タイトル: {a.get("title")}
本文:
{a.get("body")}

"""

        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=120,
        )

        res.raise_for_status()
        body = res.json()["choices"][0]["message"]["content"].replace("\n", "<br>")

        out = f"""
        <div style="
            font-family:'Meiryo UI', sans-serif; 
            line-height:1.7; 
            padding:22px; 
            color:#333; 
            border-bottom:1px solid #ddd;
        ">
        
            <h2 style="color:#0055a5; margin-bottom:10px;">■{label}</h2>
            <div style="margin-bottom:14px;">{body}</div>
        """

        for i, a in enumerate(articles, 1):
            date_only = a["date"].split(" ")[0] if a.get("date") else "不明"
            out += f"""
            <div style="margin-bottom:8px;">
                <strong>{i}.</strong> <a href="{a["url"]}">{a["title"]}</a><br>
                <span style="font-size:12px; color:#666;">Published: {date_only} | Source: {a["source"]}</span>
            </div>
            """

        out += "</div><br>"
        return out

    except requests.RequestException:
        return f"<b> ■{label}</b><br>GPTエラー<br><br>"


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

        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=120,
        )

        res.raise_for_status()
        summary = res.json()["choices"][0]["message"]["content"].replace("\n", "<br>")

        return f"""
        <div style="font-family:'Meiryo UI', sans-serif; padding:20px; background:#f5f7fa; border:1px solid #ddd; margin-bottom:24px; color:#333;">
            <h2 style="margin-top:0;">■ 本日のニュースサマリ</h2>
            <div style="line-height:1.7;">{summary}</div>
        </div>
        """

    except requests.RequestException:
        return "<b>■本日のニュースサマリ</b><br>生成できませんでした<br><br>"
