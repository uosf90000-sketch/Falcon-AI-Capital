"""
Alpaca Halal Trader — تداول إسلامي 100%
كل أمر شراء يمر عبر Musaffa قبل التنفيذ.
تطهير > 0% = رفض تلقائي بدون استثناء.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

from musaffa_client import MusaffaClient

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    success: bool
    ticker: str
    side: str               # "buy" | "sell"
    qty: float
    order_id: str = ""
    reason: str = ""        # سبب الرفض إذا success=False


class AlpacaHalalTrader:
    """
    غلاف حول Alpaca يضيف:
      1. فحص Musaffa قبل كل شراء
      2. تصفية قائمة الأسهم المرشحة
      3. مراجعة المحفظة الحالية
    """

    def __init__(
        self,
        api_key: str = "",
        secret_key: str = "",
        paper: bool = True,
        musaffa_key: str = "",
    ):
        api_key    = api_key    or os.getenv("ALPACA_API_KEY", "")
        secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY", "")

        self.trading = TradingClient(api_key, secret_key, paper=paper)
        self.data    = StockHistoricalDataClient(api_key, secret_key)
        self.musaffa = MusaffaClient(api_key=musaffa_key)

        mode = "PAPER" if paper else "LIVE"
        logger.info(f"AlpacaHalalTrader initialized [{mode}]")

    # ── شراء ─────────────────────────────────────────────────────────────────

    def buy(self, ticker: str, qty: float, limit_price: float = 0.0) -> OrderResult:
        """
        يشتري السهم فقط إذا كان حلال 100% من Musaffa.
        limit_price > 0 → limit order | limit_price = 0 → market order
        """
        ticker = ticker.upper().strip()

        # ── فحص شرعي أولاً ───────────────────────────────────────────────────
        check = self.musaffa.is_halal_zero(ticker)
        if not check["halal"]:
            logger.warning(f"BUY BLOCKED | {ticker} | {check['reason']}")
            return OrderResult(
                success=False, ticker=ticker, side="buy", qty=qty,
                reason=f"مرفوض شرعاً: {check['reason']}"
            )

        # ── تنفيذ الأمر ───────────────────────────────────────────────────────
        try:
            if limit_price > 0:
                req = LimitOrderRequest(
                    symbol=ticker, qty=qty,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                    limit_price=round(limit_price, 2),
                )
            else:
                req = MarketOrderRequest(
                    symbol=ticker, qty=qty,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                )

            order = self.trading.submit_order(req)
            logger.info(f"BUY OK | {ticker} x{qty} | order={order.id}")
            return OrderResult(
                success=True, ticker=ticker, side="buy",
                qty=qty, order_id=str(order.id)
            )

        except Exception as e:
            logger.error(f"BUY ERROR | {ticker}: {e}")
            return OrderResult(
                success=False, ticker=ticker, side="buy", qty=qty,
                reason=f"خطأ Alpaca: {e}"
            )

    # ── بيع ──────────────────────────────────────────────────────────────────

    def sell(self, ticker: str, qty: float) -> OrderResult:
        """البيع لا يحتاج فحص شرعي — نبيع أي سهم موجود."""
        ticker = ticker.upper().strip()
        try:
            req = MarketOrderRequest(
                symbol=ticker, qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
            order = self.trading.submit_order(req)
            logger.info(f"SELL OK | {ticker} x{qty} | order={order.id}")
            return OrderResult(
                success=True, ticker=ticker, side="sell",
                qty=qty, order_id=str(order.id)
            )
        except Exception as e:
            logger.error(f"SELL ERROR | {ticker}: {e}")
            return OrderResult(
                success=False, ticker=ticker, side="sell", qty=qty,
                reason=f"خطأ Alpaca: {e}"
            )

    def sell_all(self, ticker: str) -> OrderResult:
        """يبيع كل الكمية المتاحة من السهم."""
        try:
            pos = self.trading.get_open_position(ticker.upper())
            qty = float(pos.qty_available)
            return self.sell(ticker, qty)
        except Exception as e:
            return OrderResult(
                success=False, ticker=ticker, side="sell", qty=0,
                reason=f"لا توجد صفقة مفتوحة: {e}"
            )

    # ── تصفية قائمة مرشحة ────────────────────────────────────────────────────

    def filter_halal(self, tickers: list[str]) -> list[str]:
        """
        يأخذ قائمة أسهم مرشحة من استراتيجية البوت
        ويرجع فقط الحلال 100%.

        الاستخدام في البوت:
            candidates = strategy.get_signals()   # أسهم البوت المرشحة
            halal_only = trader.filter_halal(candidates)
            for ticker in halal_only:
                trader.buy(ticker, qty=1)
        """
        result = self.musaffa.screen_list(tickers)
        if result["rejected"]:
            for t, reason in result["rejected"].items():
                logger.info(f"FILTERED OUT | {t}: {reason}")
        logger.info(
            f"filter_halal: {result['halal_count']}/{result['total']} passed"
        )
        return result["halal"]

    # ── مراجعة المحفظة ────────────────────────────────────────────────────────

    def audit_portfolio(self) -> dict:
        """
        يراجع المحفظة الحالية ويكشف أي سهم أصبح غير متوافق.
        يُشغَّل يومياً أو عند تغيير حالة Musaffa.

        Returns:
            {
                "clean":    ["PANW", "CRWD"],
                "flagged":  {"AAPL": "سبب"},
                "unknown":  ["XYZ"]
            }
        """
        try:
            positions = self.trading.get_all_positions()
        except Exception as e:
            logger.error(f"Could not fetch positions: {e}")
            return {"clean": [], "flagged": {}, "unknown": []}

        clean, flagged, unknown = [], {}, []

        for pos in positions:
            ticker = pos.symbol
            check  = self.musaffa.is_halal_zero(ticker)

            if check["status"] == "UNKNOWN":
                unknown.append(ticker)
                logger.warning(f"AUDIT UNKNOWN | {ticker}")
            elif check["halal"]:
                clean.append(ticker)
            else:
                flagged[ticker] = check["reason"]
                logger.warning(f"AUDIT FLAGGED | {ticker}: {check['reason']}")

        logger.info(
            f"Portfolio audit: {len(clean)} clean | "
            f"{len(flagged)} flagged | {len(unknown)} unknown"
        )
        return {"clean": clean, "flagged": flagged, "unknown": unknown}

    # ── معلومات الحساب ────────────────────────────────────────────────────────

    def get_account_summary(self) -> dict:
        acc = self.trading.get_account()
        return {
            "buying_power":  float(acc.buying_power),
            "portfolio_value": float(acc.portfolio_value),
            "cash":          float(acc.cash),
            "status":        acc.status,
        }

    def get_latest_price(self, ticker: str) -> Optional[float]:
        try:
            req  = StockLatestQuoteRequest(symbol_or_symbols=ticker.upper())
            data = self.data.get_stock_latest_quote(req)
            q    = data[ticker.upper()]
            return float(q.ask_price or q.bid_price or 0)
        except Exception as e:
            logger.warning(f"Price fetch failed for {ticker}: {e}")
            return None
