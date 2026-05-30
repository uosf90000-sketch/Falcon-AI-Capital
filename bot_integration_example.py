"""
مثال دمج AlpacaHalalTrader مع بوت التداول الحالي.
انسخ ما يناسب بوتك وأضفه على كوده.
"""

from alpaca_halal_trader import AlpacaHalalTrader

# ── إعداد (مرة واحدة عند بدء البوت) ─────────────────────────────────────────
trader = AlpacaHalalTrader(paper=True)   # paper=False للتداول الحقيقي


# ══════════════════════════════════════════════════════════════════════════════
# 1. قبل كل شراء — تحقق شرعي تلقائي
# ══════════════════════════════════════════════════════════════════════════════

result = trader.buy("PANW", qty=1)

if result.success:
    print(f"✅ اشترينا {result.ticker} | order: {result.order_id}")
else:
    print(f"❌ رُفض {result.ticker}: {result.reason}")

# AAPL مثال: سيُرفض تلقائياً (فيه تطهير)
result = trader.buy("AAPL", qty=1)
# ← ❌ رُفض AAPL: نسبة تطهير 1.5% — يجب أن تكون 0%


# ══════════════════════════════════════════════════════════════════════════════
# 2. البوت يختار أسهم → نصفيها قبل الشراء
# ══════════════════════════════════════════════════════════════════════════════

# مثال: استراتيجيتك ترشح هذه الأسهم (momentum, AI signals, إلخ)
bot_candidates = ["PANW", "CRWD", "AAPL", "NVDA", "FTNT", "JPM", "ZS"]

# خطوة واحدة تحذف الحرام والمشبوه
halal_candidates = trader.filter_halal(bot_candidates)
print(f"الأسهم الحلال من المرشحين: {halal_candidates}")
# ← ['PANW', 'CRWD', 'FTNT', 'ZS']

# الآن اشتري من الحلال فقط
account = trader.get_account_summary()
budget_per_stock = account["buying_power"] / len(halal_candidates) if halal_candidates else 0

for ticker in halal_candidates:
    price = trader.get_latest_price(ticker)
    if price and price > 0:
        qty = int(budget_per_stock / price)
        if qty >= 1:
            trader.buy(ticker, qty=qty)


# ══════════════════════════════════════════════════════════════════════════════
# 3. مراجعة يومية للمحفظة (شغّلها صباح كل يوم)
# ══════════════════════════════════════════════════════════════════════════════

audit = trader.audit_portfolio()

if audit["flagged"]:
    print("⚠️ أسهم تغيّرت حالتها الشرعية — يجب بيعها:")
    for ticker, reason in audit["flagged"].items():
        print(f"  {ticker}: {reason}")
        trader.sell_all(ticker)   # بيع فوري

if audit["unknown"]:
    print(f"❓ أسهم غير معروفة — راجعها يدوياً: {audit['unknown']}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. بيع عادي (لا يحتاج فحص)
# ══════════════════════════════════════════════════════════════════════════════

trader.sell("PANW", qty=1)
trader.sell_all("CRWD")   # بيع كل الكمية
