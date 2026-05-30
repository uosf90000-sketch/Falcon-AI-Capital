import sys
import os
import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify
from filters import sharia_list

app  = Flask(__name__)
NY   = ZoneInfo("America/New_York")

# ── جلب الأسعار من Yahoo Finance (مجاني بدون مفتاح) ──────────────────────────

def get_prices(tickers: list[str]) -> dict:
    """يجلب السعر الحالي والتغيّر اليومي لقائمة أسهم."""
    result = {}
    symbols = ",".join(tickers)
    url = (
        f"https://query1.finance.yahoo.com/v7/finance/quote"
        f"?symbols={symbols}&fields=regularMarketPrice,regularMarketChangePercent,shortName"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        quotes = data.get("quoteResponse", {}).get("result", [])
        for q in quotes:
            sym = q.get("symbol", "")
            result[sym] = {
                "price":  round(q.get("regularMarketPrice", 0), 2),
                "change": round(q.get("regularMarketChangePercent", 0), 2),
                "name":   q.get("shortName", sym),
            }
    except Exception:
        pass
    return result

# ── الأسهم الحلال المعتمدة ────────────────────────────────────────────────────

HALAL_TICKERS = sorted(sharia_list.ZERO_PURIFICATION)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/check", methods=["POST"])
def check():
    ticker = request.json.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "أدخل رمز السهم"})
    result = sharia_list.check(ticker)
    return jsonify({
        "ticker":       ticker,
        "decision":     result["decision"],
        "halal":        result["decision"] == "BUY_ALLOWED",
        "reason":       result["reason"],
        "purification": result["purification"],
    })

@app.route("/daily")
def daily():
    """أسهم اليوم — الحلال النقية مع الأسعار."""
    prices   = get_prices(HALAL_TICKERS)
    now_ny   = datetime.now(NY)
    today    = now_ny.strftime("%A، %d %B %Y")

    stocks = []
    for t in HALAL_TICKERS:
        p = prices.get(t, {})
        stocks.append({
            "ticker": t,
            "name":   p.get("name", t),
            "price":  p.get("price", 0),
            "change": p.get("change", 0),
        })

    # رتّب: الأكثر ارتفاعاً أولاً
    stocks.sort(key=lambda x: x["change"], reverse=True)

    return render_template("daily.html", stocks=stocks, today=today, count=len(stocks))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
