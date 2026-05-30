"""
Musaffa API Client — يجلب الأسهم الحلال 100% (تطهير صفر)
وثائق API: https://musaffa.com/developers
"""

import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

MUSAFFA_BASE = "https://api.musaffa.com/v1"


class MusaffaClient:

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("MUSAFFA_API_KEY", "")
        self._session = requests.Session()
        self._session.headers.update({
            "apiKey": self.api_key,
            "Accept": "application/json",
            "User-Agent": "FalconAICapital/1.0",
        })

    def get_compliance(self, ticker: str) -> Optional[dict]:
        """
        يجلب بيانات الامتثال الشرعي من Musaffa.
        يرجع None إذا فشل الطلب أو لم يوجد السهم.

        الشرط: shariaComplianceStatus == "COMPLIANT" و purificationPercentage == 0.0
        """
        try:
            resp = self._session.get(
                f"{MUSAFFA_BASE}/instruments/{ticker.upper()}",
                timeout=10,
            )
            if resp.status_code == 404:
                logger.info(f"Musaffa: {ticker} غير موجود")
                return None
            if resp.status_code in (401, 403):
                logger.error("Musaffa: مفتاح API غير صالح أو منتهي")
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning(f"Musaffa request error for {ticker}: {e}")
            return None

    def is_halal_zero(self, ticker: str) -> dict:
        """
        يتحقق إذا السهم حلال 100% (متوافق + تطهير صفر).

        Returns:
            {
                "ticker": "PANW",
                "halal": True,
                "purification_rate": 0.0,
                "status": "COMPLIANT",
                "sector": "Technology",
                "reason": ""
            }
        """
        data = self.get_compliance(ticker)
        if data is None:
            return {
                "ticker": ticker,
                "halal": False,
                "purification_rate": None,
                "status": "UNKNOWN",
                "sector": "",
                "reason": "لا توجد بيانات في Musaffa",
            }

        status = data.get("shariaComplianceStatus", "")
        purification = float(data.get("purificationPercentage") or 0)
        halal = status == "COMPLIANT" and purification == 0.0

        reason = ""
        if not halal:
            if status != "COMPLIANT":
                reason = f"الحالة: {status}"
            else:
                reason = f"نسبة تطهير {purification}% — يجب أن تكون 0%"

        return {
            "ticker": ticker,
            "halal": halal,
            "purification_rate": purification,
            "status": status,
            "sector": data.get("businessSector", ""),
            "reason": reason,
        }

    def screen_list(self, tickers: list[str]) -> dict:
        """
        يفلتر قائمة أسهم ويرجع الحلال الصرف فقط.

        Returns:
            {
                "halal": ["PANW", "CRWD"],
                "rejected": {"AAPL": "نسبة تطهير 1.5%", ...},
                "total": 10,
                "halal_count": 2
            }
        """
        halal = []
        rejected = {}
        for ticker in tickers:
            result = self.is_halal_zero(ticker)
            if result["halal"]:
                halal.append(ticker)
            else:
                rejected[ticker] = result["reason"]

        return {
            "halal": halal,
            "rejected": rejected,
            "total": len(tickers),
            "halal_count": len(halal),
        }
