"""
Falcon AI Capital — Sharia Trading Bot
البوت لا يُنفّذ أي شراء إلا إذا كان السهم BUY_ALLOWED.

الاستخدام:
  python bot/sharia_bot.py

متغيرات البيئة المطلوبة:
  ALPACA_KEY        مفتاح Alpaca API
  ALPACA_SECRET     سر Alpaca API
  ZOYA_KEY          مفتاح Zoya (اختياري — للفلتر الشرعي)
  FLTRNA_KEY        مفتاح Fltrna (اختياري)
  ALPACA_PAPER      true/false (افتراضي: true)
"""

import os
import logging
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from brokers.alpaca_broker import AlpacaBroker
from filters.islamic_filter import IslamicFilter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── إعدادات البوت ─────────────────────────────────────────────────────────────

# الأسهم المرشحة للتداول (بعد الفلتر الشرعي)
WATCHLIST = [
    "PANW", "CRWD", "FTNT", "ZS",        # أمن سيبراني
    "ANSS", "SNPS", "CDNS",               # برامج هندسية
    "IDXX", "PODD",                        # رعاية صحية
    "ROK", "NOVT",                         # صناعية
]

# حجم الصفقة (بالدولار)
ORDER_SIZE_USD = 100.0


class ShariaBot:

    def __init__(self):
        alpaca_key    = os.getenv("ALPACA_KEY", "")
        alpaca_secret = os.getenv("ALPACA_SECRET", "")
        zoya_key      = os.getenv("ZOYA_KEY", "")
        fltrna_key    = os.getenv("FLTRNA_KEY", "")
        paper         = os.getenv("ALPACA_PAPER", "true").lower() != "false"

        if not alpaca_key or not alpaca_secret:
            raise ValueError("ALPACA_KEY و ALPACA_SECRET مطلوبان")

        self.broker = AlpacaBroker(alpaca_key, alpaca_secret, paper=paper)
        self.filter = IslamicFilter(
            zoya_api_key=zoya_key,
            musaffa_api_key=fltrna_key,
        )

    def run(self):
        logger.info("=" * 55)
        logger.info("  Falcon AI Capital — Sharia Bot")
        logger.info("=" * 55)

        # ① عرض حالة الحساب
        account = self.broker.get_account()
        logger.info(
            f"الحساب: cash=${account['cash']:,.0f} | "
            f"portfolio=${account['portfolio_value']:,.0f} | "
            f"buying_power=${account['buying_power']:,.0f}"
        )

        if account["cash"] < ORDER_SIZE_USD:
            logger.warning("رصيد غير كافٍ — لا يمكن التداول")
            return

        # ② فلترة الأسهم شرعياً
        logger.info(f"\nفحص {len(WATCHLIST)} سهم شرعياً ...")
        halal_tickers = self.filter.filter_list(WATCHLIST)

        logger.info(f"\nالأسهم الحلال بتطهير 0%: {halal_tickers}")
        rejected = set(WATCHLIST) - set(halal_tickers)
        logger.info(f"المرفوضة شرعياً:           {sorted(rejected)}")

        if not halal_tickers:
            logger.warning("لا توجد أسهم حلال متاحة — البوت متوقف")
            return

        # ③ تنفيذ الشراء للأسهم الحلال فقط
        logger.info("\nتنفيذ الأوردرات ...")
        for ticker in halal_tickers:
            self._execute_buy(ticker, account["buying_power"])

        # ④ عرض المراكز الحالية
        self._show_positions()

    def _execute_buy(self, ticker: str, buying_power: float):
        if not self.broker.is_tradable(ticker):
            logger.warning(f"{ticker}: غير متاح للتداول على Alpaca")
            return

        try:
            # احسب عدد الأسهم (أوردر جزئي)
            from alpaca.data.historical import StockHistoricalDataClient
            qty = ORDER_SIZE_USD  # notional بالدولار
        except Exception:
            qty = 1

        logger.info(f"شراء {ticker} بـ ${ORDER_SIZE_USD} ...")
        result = self.broker.buy(ticker, qty=None)  # سيُستخدم notional
        if result:
            logger.info(f"  ✅ تم الشراء | order_id={result['order_id']}")
        else:
            logger.error(f"  ❌ فشل الشراء {ticker}")

    def _show_positions(self):
        positions = self.broker.get_positions()
        if not positions:
            logger.info("\nلا توجد مراكز مفتوحة")
            return
        logger.info("\nالمراكز الحالية:")
        for p in positions:
            pl_sign = "+" if p["unrealized_pl"] >= 0 else ""
            logger.info(
                f"  {p['ticker']:<8} qty={p['qty']:.2f} | "
                f"value=${p['market_value']:,.0f} | "
                f"P&L={pl_sign}${p['unrealized_pl']:,.0f}"
            )


if __name__ == "__main__":
    ShariaBot().run()
