"""
Alpaca Broker — Falcon AI Capital
تنفيذ الأوردرات عبر Alpaca بعد الفلتر الشرعي.
"""

import logging
from typing import Optional
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetAssetsRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass

logger = logging.getLogger(__name__)


class AlpacaBroker:

    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self.client = TradingClient(
            api_key=api_key,
            secret_key=secret_key,
            paper=paper,
        )
        mode = "Paper" if paper else "Live"
        logger.info(f"AlpacaBroker initialized [{mode}]")

    def get_account(self) -> dict:
        acc = self.client.get_account()
        return {
            "cash": float(acc.cash),
            "portfolio_value": float(acc.portfolio_value),
            "buying_power": float(acc.buying_power),
            "status": acc.status,
        }

    def get_positions(self) -> list[dict]:
        positions = self.client.get_all_positions()
        return [
            {
                "ticker": p.symbol,
                "qty": float(p.qty),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
            }
            for p in positions
        ]

    def buy(self, ticker: str, qty: float) -> Optional[dict]:
        """يشتري سهم بعدد محدد."""
        try:
            order = self.client.submit_order(MarketOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            ))
            logger.info(f"BUY {ticker} qty={qty} | order_id={order.id}")
            return {"order_id": str(order.id), "status": str(order.status)}
        except Exception as e:
            logger.error(f"BUY failed for {ticker}: {e}")
            return None

    def sell(self, ticker: str, qty: float) -> Optional[dict]:
        """يبيع سهم بعدد محدد."""
        try:
            order = self.client.submit_order(MarketOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            ))
            logger.info(f"SELL {ticker} qty={qty} | order_id={order.id}")
            return {"order_id": str(order.id), "status": str(order.status)}
        except Exception as e:
            logger.error(f"SELL failed for {ticker}: {e}")
            return None

    def sell_all(self, ticker: str) -> Optional[dict]:
        """يبيع كامل حصة السهم."""
        try:
            self.client.close_position(ticker)
            logger.info(f"SELL ALL {ticker}")
            return {"status": "closed"}
        except Exception as e:
            logger.error(f"SELL ALL failed for {ticker}: {e}")
            return None

    def is_tradable(self, ticker: str) -> bool:
        try:
            asset = self.client.get_asset(ticker)
            return asset.tradable and asset.status == "active"
        except Exception:
            return False
