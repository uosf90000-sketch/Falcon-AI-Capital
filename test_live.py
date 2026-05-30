"""
اختبار شامل للأسهم — يستخدم Zoya أو Musaffa
شغّله:
  python test_live.py                          ← Musaffa بدون مفتاح
  ZOYA_KEY=مفتاحك python test_live.py          ← Zoya API الحقيقي
"""

import os
import sys
import requests

ZOYA_KEY = os.getenv("ZOYA_KEY", "")

TEST_TICKERS = [
    # أمن سيبراني
    "PANW", "CRWD", "FTNT", "ZS", "OKTA",
    # برامج هندسية
    "ANSS", "SNPS", "CDNS",
    # تكنولوجيا (متوقع تطهير)
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    # بنوك / حرام
    "JPM", "BAC", "GS",
    # رعاية صحية
    "IDXX", "PODD",
]


def check_zoya(ticker: str) -> dict | None:
    query = """
    query StockReport($ticker: String!) {
      stockReport(ticker: $ticker) {
        ticker complianceStatus purificationRatio businessSector
      }
    }
    """
    try:
        r = requests.post(
            "https://api.zoya.finance/graphql",
            json={"query": query, "variables": {"ticker": ticker}},
            headers={"Authorization": f"Bearer {ZOYA_KEY}",
                     "Content-Type": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        d = r.json().get("data", {}).get("stockReport") or {}
        if not d:
            return None
        purification = round(float(d.get("purificationRatio") or 0) * 100, 4)
        return {
            "source": "Zoya",
            "status": str(d.get("complianceStatus") or "").upper(),
            "purification": purification,
            "sector": d.get("businessSector", "—"),
        }
    except Exception as e:
        return {"error": str(e)}


def check_musaffa(ticker: str) -> dict | None:
    try:
        r = requests.get(
            f"https://api.musaffa.com/v1/stocks/{ticker}/compliance",
            timeout=10,
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        d = r.json()
        purification = round(float(d.get("purificationPercentage") or 0), 4)
        return {
            "source": "Musaffa",
            "status": str(d.get("complianceStatus") or "").upper(),
            "purification": purification,
            "sector": d.get("sector", "—"),
        }
    except Exception as e:
        return {"error": str(e)}


def main():
    use_zoya = bool(ZOYA_KEY)
    source_name = "Zoya (حقيقي)" if use_zoya else "Musaffa (مجاني)"
    checker = check_zoya if use_zoya else check_musaffa

    print(f"\n{'='*62}")
    print(f"  فلتر الأسهم الإسلامي — المصدر: {source_name}")
    print(f"{'='*62}")
    print(f"  {'السهم':<8} {'القرار':<22} {'الحالة':<16} {'تطهير':>7}  {'القطاع'}")
    print(f"  {'-'*58}")

    buy_allowed = []
    sharia_rejected = []

    for ticker in TEST_TICKERS:
        data = checker(ticker)

        if data is None or "error" in (data or {}):
            err = (data or {}).get("error", "لا بيانات")
            print(f"  {ticker:<8} {'❓ NO DATA':<22} —  {err[:30]}")
            continue

        status = data["status"]
        purification = data["purification"]
        sector = data.get("sector", "—")

        if status == "COMPLIANT" and purification == 0.0:
            decision = "✅ BUY_ALLOWED"
            buy_allowed.append(ticker)
        else:
            decision = "❌ SHARIA_REJECTED"
            sharia_rejected.append(ticker)

        print(f"  {ticker:<8} {decision:<22} {status:<16} {purification:>6}%  {sector}")

    print(f"\n{'='*62}")
    print(f"  ✅ BUY_ALLOWED    : {buy_allowed}")
    print(f"  ❌ SHARIA_REJECTED: {sharia_rejected}")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    main()
