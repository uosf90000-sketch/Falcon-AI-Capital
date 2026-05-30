"""
Falcon AI Capital — البوت الكامل
─────────────────────────────────
المنطق:
  1. يفحص كل سهم في الـ WATCHLIST
  2. يتحقق من الحلال 100% (Zoya أو القائمة المحلية)
  3. يدرس السهم: سعر + زخم + حجم
  4. إذا كل الشروط اجتمعت → يشتري عبر Alpaca
  5. يراقب المراكز ويبيع عند الهدف أو وقف الخسارة

الاستخدام:
  ALPACA_KEY=xxx ALPACA_SECRET=yyy python run_bot.py
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from filters.islamic_filter import IslamicFilter, KNOWN_HARAM, HALAL_WITH_PURIFICATION

logger = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")

# ══════════════════════════════════════════════════════════════════════════════
#  إعدادات البوت — عدّلها حسب رغبتك
# ══════════════════════════════════════════════════════════════════════════════

WATCHLIST = [
    # أمن سيبراني
    "PANW", "CRWD", "FTNT", "ZS", "OKTA",
    # برامج هندسية
    "ANSS", "SNPS", "CDNS", "PTC",
    # رعاية صحية
    "IDXX", "PODD", "INSP",
    # صناعية
    "ROK", "NOVT",
    # طاقة متجددة
    "NEE", "CWEN",
]

ORDER_SIZE_USD   = 200.0    # حجم كل صفقة بالدولار
MAX_POSITIONS    = 5        # أقصى عدد مراكز مفتوحة في نفس الوقت
TAKE_PROFIT_PCT  = 5.0      # هدف الربح %
STOP_LOSS_PCT    = 2.0      # وقف الخسارة %

# شروط الشراء التقني
MA_PERIOD        = 20       # المتوسط المتحرك
RSI_PERIOD       = 14
RSI_MAX          = 65       # لا نشتري إذا RSI فوق هذا (مبالغ فيه)
MIN_VOLUME_RATIO = 1.2      # الحجم يجب أكبر من المتوسط × هذه النسبة


# ══════════════════════════════════════════════════════════════════════════════

class FalconBot:

    def __init__(self):
        api_key    = os.environ["ALPACA_KEY"]
        secret_key = os.environ["ALPACA_SECRET"]
        zoya_key   = os.getenv("ZOYA_KEY", "")
        paper      = os.getenv("ALPACA_PAPER", "true").lower() != "false"

        self.trade  = TradingClient(api_key, secret_key, paper=paper)
        self.data   = StockHistoricalDataClient(api_key, secret_key)
        self.filter = IslamicFilter(zoya_api_key=zoya_key)

        mode = "📄 Paper" if paper else "💵 Live"
        logger.info(f"FalconBot جاهز [{mode}]")

    # ── الحلقة الرئيسية ────────────────────────────────────────────────────

    def run(self):
        logger.info("=" * 60)
        logger.info("  Falcon AI Capital — Sharia Trading Bot")
        logger.info("=" * 60)

        acc = self.trade.get_account()
        logger.info(
            f"الحساب | cash=${float(acc.cash):,.0f} | "
            f"portfolio=${float(acc.portfolio_value):,.0f} | "
            f"buying_power=${float(acc.buying_power):,.0f}"
        )

        # ① إدارة المراكز الحالية (بيع عند الهدف أو وقف الخسارة)
        self._manage_positions()

        # ② البحث عن فرص جديدة
        open_count = len(self.trade.get_all_positions())
        if open_count >= MAX_POSITIONS:
            logger.info(f"وصلنا للحد الأقصى ({MAX_POSITIONS} مراكز) — لا شراء جديد")
            return

        if float(acc.buying_power) < ORDER_SIZE_USD:
            logger.info("القوة الشرائية غير كافية")
            return

        # ③ فحص الأسهم وشراء
        self._scan_and_buy(open_count)

    # ── إدارة المراكز ──────────────────────────────────────────────────────

    def _manage_positions(self):
        positions = self.trade.get_all_positions()
        if not positions:
            return

        logger.info(f"\nمراجعة {len(positions)} مركز مفتوح ...")
        for pos in positions:
            ticker   = pos.symbol
            pl_pct   = float(pos.unrealized_plpc) * 100

            if pl_pct >= TAKE_PROFIT_PCT:
                logger.info(f"  ✅ هدف الربح: {ticker} +{pl_pct:.1f}% → بيع")
                self._sell(ticker)

            elif pl_pct <= -STOP_LOSS_PCT:
                logger.info(f"  🛑 وقف الخسارة: {ticker} {pl_pct:.1f}% → بيع")
                self._sell(ticker)

            else:
                logger.info(
                    f"  ⏳ {ticker:<8} P&L={pl_pct:+.1f}%  "
                    f"value=${float(pos.market_value):,.0f}"
                )

    # ── فحص الأسهم وشراء ───────────────────────────────────────────────────

    def _scan_and_buy(self, open_count: int):
        logger.info(f"\nفحص {len(WATCHLIST)} سهم ...")

        # الأسهم المفتوحة حالياً (لا نكرر)
        open_symbols = {p.symbol for p in self.trade.get_all_positions()}

        bought = 0
        for ticker in WATCHLIST:
            if open_count + bought >= MAX_POSITIONS:
                break
            if ticker in open_symbols:
                continue

            result = self._evaluate(ticker)
            if result["buy"]:
                success = self._buy(ticker)
                if success:
                    bought += 1
                    time.sleep(0.5)

        logger.info(f"\nتم شراء {bought} سهم جديد")

    # ── تقييم السهم ────────────────────────────────────────────────────────

    def _evaluate(self, ticker: str) -> dict:
        """
        يفحص السهم على ثلاث مراحل:
          1. الفلتر الشرعي (إلزامي — رفض فوري إذا فشل)
          2. التحليل التقني (MA + RSI + Volume)
          3. القرار النهائي
        """

        # ① الفلتر الشرعي
        sharia = self._check_sharia(ticker)
        if not sharia["halal"]:
            logger.info(f"  ❌ {ticker:<8} SHARIA_REJECTED — {sharia['reason']}")
            return {"buy": False}

        # ② التحليل التقني
        tech = self._check_technical(ticker)
        if tech is None:
            logger.info(f"  ❓ {ticker:<8} لا توجد بيانات تقنية")
            return {"buy": False}

        passed = tech["above_ma"] and tech["rsi"] < RSI_MAX and tech["volume_ok"]

        status = (
            f"MA={'✓' if tech['above_ma'] else '✗'}  "
            f"RSI={tech['rsi']:.0f}({'✓' if tech['rsi']<RSI_MAX else '✗'})  "
            f"Vol={'✓' if tech['volume_ok'] else '✗'}"
        )

        if passed:
            logger.info(f"  ✅ {ticker:<8} BUY_ALLOWED | {status}")
        else:
            logger.info(f"  ⏭  {ticker:<8} شروط تقنية غير مكتملة | {status}")

        return {"buy": passed}

    # ── الفلتر الشرعي ──────────────────────────────────────────────────────

    def _check_sharia(self, ticker: str) -> dict:
        # رفض فوري من القائمة المحلية (بدون API)
        if ticker in KNOWN_HARAM:
            return {"halal": False, "reason": "حرام (قائمة محلية)"}
        if ticker in HALAL_WITH_PURIFICATION:
            return {"halal": False, "reason": "به نسبة تطهير"}

        # فحص API إذا كان هناك مفتاح
        result = self.filter.is_halal(ticker)
        return {
            "halal": result["halal"],
            "reason": result.get("reason", ""),
        }

    # ── التحليل التقني ─────────────────────────────────────────────────────

    def _check_technical(self, ticker: str) -> dict | None:
        try:
            end   = datetime.now(NY)
            start = end - timedelta(days=60)

            bars = self.data.get_stock_bars(StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
            ))
            df = bars.df
            if df.empty or len(df) < MA_PERIOD + 5:
                return None

            # إذا MultiIndex، خذ السهم المطلوب فقط
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(ticker, level="symbol")

            close  = df["close"]
            volume = df["volume"]

            # المتوسط المتحرك
            ma       = close.rolling(MA_PERIOD).mean().iloc[-1]
            price    = close.iloc[-1]
            above_ma = price > ma

            # RSI
            delta = close.diff()
            gain  = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
            loss  = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
            rs    = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 100
            rsi   = 100 - (100 / (1 + rs))

            # الحجم
            avg_vol    = volume.rolling(20).mean().iloc[-1]
            today_vol  = volume.iloc[-1]
            volume_ok  = today_vol > avg_vol * MIN_VOLUME_RATIO

            return {
                "price":     price,
                "ma":        ma,
                "above_ma":  above_ma,
                "rsi":       rsi,
                "volume_ok": volume_ok,
            }
        except Exception as e:
            logger.warning(f"Technical check failed for {ticker}: {e}")
            return None

    # ── تنفيذ الشراء ───────────────────────────────────────────────────────

    def _buy(self, ticker: str) -> bool:
        try:
            order = self.trade.submit_order(MarketOrderRequest(
                symbol=ticker,
                notional=ORDER_SIZE_USD,    # بالدولار (fractional shares)
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            ))
            logger.info(
                f"  📥 شراء {ticker} بـ ${ORDER_SIZE_USD} | "
                f"order_id={str(order.id)[:8]}..."
            )
            return True
        except Exception as e:
            logger.error(f"  فشل شراء {ticker}: {e}")
            return False

    # ── تنفيذ البيع ────────────────────────────────────────────────────────

    def _sell(self, ticker: str) -> bool:
        try:
            self.trade.close_position(ticker)
            logger.info(f"  📤 بيع كامل {ticker}")
            return True
        except Exception as e:
            logger.error(f"  فشل بيع {ticker}: {e}")
            return False
