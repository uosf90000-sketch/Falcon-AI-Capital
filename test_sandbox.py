"""
اختبار Zoya Sandbox API
الـ endpoint: https://sandbox-api.zoya.finance/graphql

شغّله هكذا:
  ZOYA_KEY=<مفتاحك> python test_sandbox.py
"""

import os
import sys
import json
import requests

SANDBOX_URL = "https://sandbox-api.zoya.finance/graphql"

ZOYA_KEY = os.getenv("ZOYA_KEY", "")

# أسهم للاختبار — مزيج من حلال/حرام/مشكوك
TEST_TICKERS = [
    "PANW", "CRWD", "FTNT",          # أمن سيبراني — متوقع حلال 0%
    "AAPL", "MSFT", "NVDA",          # تكنولوجيا — بتطهير
    "JPM", "BAC",                     # بنوك — حرام
    "ANSS", "SNPS",                   # برامج هندسية — متوقع حلال 0%
]


def query_zoya(ticker: str, api_key: str) -> dict | None:
    query = """
    query StockReport($ticker: String!) {
      stockReport(ticker: $ticker) {
        ticker
        complianceStatus
        purificationRatio
        businessSector
      }
    }
    """
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        resp = requests.post(
            SANDBOX_URL,
            json={"query": query, "variables": {"ticker": ticker}},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("stockReport")
    except Exception as e:
        print(f"  ⚠️  خطأ: {e}")
        return None


def run_sandbox_test():
    print(f"\n{'='*55}")
    print(f"  Zoya Sandbox Test")
    print(f"  {SANDBOX_URL}")
    print(f"{'='*55}\n")

    if not ZOYA_KEY:
        print("⚠️  لم يتم تعيين ZOYA_KEY — سيعمل بدون مصادقة\n")

    results = {"buy_allowed": [], "rejected": [], "error": []}

    for ticker in TEST_TICKERS:
        data = query_zoya(ticker, ZOYA_KEY)
        if data is None:
            print(f"  ❓ {ticker:<8} — لا توجد بيانات")
            results["error"].append(ticker)
            continue

        status = str(data.get("complianceStatus") or "").upper()
        ratio_raw = data.get("purificationRatio")
        purification = round(float(ratio_raw or 0) * 100, 4)
        sector = data.get("businessSector", "—")

        if status == "COMPLIANT" and purification == 0.0:
            icon = "✅ BUY_ALLOWED"
            results["buy_allowed"].append(ticker)
        else:
            icon = "❌ SHARIA_REJECTED"
            results["rejected"].append(ticker)

        reason = ""
        if status != "COMPLIANT":
            reason = f"status={status}"
        elif purification > 0:
            reason = f"purification={purification}%"

        print(f"  {icon:<22} {ticker:<8} | {status:<15} | {purification:>5}% | {sector}")
        if reason:
            print(f"  {'':>22} {'':>8}   ↳ {reason}")

    print(f"\n{'='*55}")
    print(f"  BUY_ALLOWED   : {results['buy_allowed']}")
    print(f"  REJECTED      : {results['rejected']}")
    print(f"  ERROR/NODATA  : {results['error']}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    run_sandbox_test()
