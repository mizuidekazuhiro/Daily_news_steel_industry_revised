import time
from datetime import datetime, timezone

import requests

from src.config.env import HEADERS
from src.domain.time_utils import JST

FX_RATES = {}


def fetch_fx_rates():
    try:
        url = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=USDJPY=X,VNDJPY=X"
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()

        results = r.json()["quoteResponse"]["result"]

        for q in results:
            if q["symbol"] == "USDJPY=X":
                FX_RATES["USD"] = q["regularMarketPrice"]
            elif q["symbol"] == "VNDJPY=X":
                FX_RATES["VND"] = q["regularMarketPrice"]

    except requests.RequestException:
        FX_RATES["USD"] = 150
        FX_RATES["VND"] = 0.006


def fetch_stock_from_quote(ticker):
    quote_url = "https://query1.finance.yahoo.com/v7/finance/quote"

    try:
        r = requests.get(
            quote_url,
            params={"symbols": ticker},
            headers=HEADERS,
            timeout=10
        )
        r.raise_for_status()

        result = r.json()["quoteResponse"]["result"]
        if not result:
            return None

        q = result[0]
        price = q.get("regularMarketPrice")
        currency = q.get("currency")
        if price is None or currency is None:
            # APIブロックやJSON構造の変更で最低限の価格情報が欠落した場合は表示できない
            return None

        market_cap = q.get("marketCap")
        ts = q.get("regularMarketTime")
        if ts is None:
            # regularMarketTimeが欠ける銘柄は存在するため、日付は任意にする
            trading_date = None
        else:
            trading_date = datetime.fromtimestamp(ts, timezone.utc)
        diff_pct = q.get("regularMarketChangePercent")
        if diff_pct is None:
            prev_close = q.get("regularMarketPreviousClose")
            if prev_close:
                diff_pct = (price - prev_close) / prev_close * 100

        return {
            "price": price,
            "diff_pct": diff_pct,
            "trading_date": trading_date,
            "market_cap": market_cap,
            "currency": currency,
            "source": "quote",
        }

    except (requests.RequestException, ValueError, KeyError):
        # JSONパース失敗や予期しないレスポンス構造のときは株価表示を諦める
        return None


def fetch_stock_snapshot(ticker):
    return fetch_stock_from_quote(ticker)


def format_market_cap(value, currency):
    if not value or not currency:
        return "不明"

    if currency == "JPY":
        if value >= 1_000_000_000_000:
            return f"¥{value/1_000_000_000_000:.1f}兆"
        return f"¥{value/100_000_000:.0f}億"

    if currency == "USD":
        usd = f"${value/1_000_000_000:.1f}B"
        jpy = value * FX_RATES.get("USD", 150)
        return f"{usd}（約¥{jpy/1_000_000_000_000:.1f}兆）"

    if currency == "VND":
        vnd = f"{value/1_000_000_000:.1f}B VND"
        jpy = value * FX_RATES.get("VND", 0.006)
        return f"{vnd}（約¥{jpy/1_000_000_000_000:.1f}兆）"

    return f"{value:,} {currency}"


def generate_stock_section():
    targets = {
        "三井物産（8031）": "8031.T",
        "大和工業（5444）": "5444.T",
        "共英製鋼（5440）": "5440.T",
        "日本製鉄（5401）": "5401.T",
        "JFEホールディングス（5411）": "5411.T",
        "Nucor（NUE）": "NUE",
        "Hoa Phat Group（HPG）": "HPG.VN",
    }

    lines = []
    snaps = []
    latest_trading_day_jp = None

    for name, ticker in targets.items():
        snap = fetch_stock_snapshot(ticker)
        if not snap:
            continue

        time.sleep(0.5)
        snaps.append(snap)

        price = snap["price"]
        diff = snap["diff_pct"]
        currency = snap["currency"]

        if currency == "JPY":
            price_str = f"¥{price:,.0f}"
        else:
            price_str = f"{price:.2f} {currency}"

        if diff is None:
            diff_html = "<span style='color:#999;'>—</span>"
        else:
            diff_str = f"{diff:+.2f}%"
            diff_html = (
                f"<span style='color:#c00;font-weight:bold;'>{diff_str}</span>"
                if abs(diff) >= 3 else
                f"<span style='color:#555;'>{diff_str}</span>"
            )

        mc_str = (
            format_market_cap(snap["market_cap"], currency)
            if snap["market_cap"] else "時価総額不明"
        )

        lines.append(
            f"<div style='margin-bottom:10px;'>"
            f"<strong>{name}</strong><br>"
            f"{price_str}（前日比 {diff_html}）<br>"
            f"時価総額 {mc_str}"
            f"</div>"
        )

    if snaps:
        dates = [s["trading_date"] for s in snaps if s.get("trading_date")]

        if dates:
            latest_trading_day_jp = (
                max(dates)
                .astimezone(JST)
                .strftime("%Y年%m月%d日")
            )
        else:
            latest_trading_day_jp = "直近営業日"

    if not lines:
        return """<div style="border-top:1px solid #ddd; margin:32px 0;"></div>
    <div style="font-family:'Meiryo UI', sans-serif; color:#888;">
        株価データを取得できた銘柄はありませんでした
    </div>"""

    price_note = f"""
    <div style="
        font-size:12px;
        color:#777;
        margin:6px 0 10px 0;
        font-family:'Meiryo UI', sans-serif;
    ">
    ※株価は{latest_trading_day_jp}の終値です（カッコ内は前営業日比％）
    </div>
    """

    fx_note = ""
    if FX_RATES:
        fx_note = (
            f"<div style=\"font-size:12px;color:#777;margin-top:6px;font-family:'Meiryo UI', sans-serif;\">"
            f"※為替前提：USD/JPY={FX_RATES.get('USD', '-'):,.2f}、"
            f"VND/JPY={FX_RATES.get('VND', '-'):,.4f}"
            f"</div>"
        )

    return f"""
    <div style="border-top:2px solid #333; margin:32px 0;"></div>
    
    <div style="
        font-size:16px;
        font-weight:bold;
        color:#555;
        font-family:'Meiryo UI', sans-serif;
        margin-bottom:8px;
    ">
    ■ 株価（前営業日終値）・時価総額
    </div>
    
    <div style="font-family:'Meiryo UI', sans-serif;">
        {price_note}
        {''.join(lines)}
        {fx_note}
    </div>
    """
