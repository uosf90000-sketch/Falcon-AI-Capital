"""
Ultra Strict Sharia Filter — Falcon AI Capital

القاعدة الذهبية (لا استثناء):
  BUY_ALLOWED فقط عندما تُحقَّق جميع الشروط:
    ✅ Zoya: COMPLIANT
    ✅ Zoya purification = 0% بالضبط
    ✅ Fltrna purification = 0% بالضبط
    ✅ كلا المصدرين متوفران
    ✅ لا تعارض بين المصدرين

  SHARIA_REJECTED في أي حالة أخرى — بلا استثناء.

مصادر البيانات المطلوبة (كلاهما إلزامي):
  1. Zoya Finance API   → الحالة الشرعية + نسبة التطهير
  2. Fltrna API        → نسبة التطهير

أسباب الرفض:
  - Zoya غير COMPLIANT
  - Zoya purification > 0%
  - Fltrna purification > 0%
  - بيانات مفقودة من أي مصدر
  - تعارض بين المصدرين
  - تعذّر التحقق من نسب التطهير
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── أسهم حرام — رفض فوري بدون API ───────────────────────────────────────────
KNOWN_HARAM = {
    # بنوك تقليدية
    "JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "TFC", "COF",
    "AXP", "DFS", "SYF", "ALLY", "RF", "FITB", "KEY", "HBAN", "CFG",
    # تأمين تقليدي
    "MET", "PRU", "AIG", "AFL", "ALL", "CB", "TRV", "PGR", "HIG",
    "LNC", "UNM", "CNO", "RLI",
    # كحول / تبغ
    "PM", "MO", "BTI", "LO", "STZ", "BUD", "TAP", "SAM",
    # قمار
    "MGM", "WYNN", "LVS", "CZR", "PENN", "DKNG", "RSI",
    # أسلحة
    "LMT", "RTX", "NOC", "GD", "BA", "L3H",
    # خنزير
    "HRL",
}

# ── أسهم حلال لكن بتطهير — رفض فوري بدون API ─────────────────────────────────
HALAL_WITH_PURIFICATION = {
    "AAPL", "NVDA", "MSFT", "GOOGL", "GOOG",
    "AMZN", "META", "TSLA", "AMGN", "GILD",
}

# التفاوت المسموح به لاعتبار المصدرين متوافقين (صفر = صرامة مطلقة)
_PURIFICATION_TOLERANCE = 0.0


def _sharia_rejected(
    ticker: str,
    reason: str,
    rejection_code: str,
    zoya: Optional[dict] = None,
    fltrna: Optional[dict] = None,
) -> dict:
    return {
        "ticker": ticker,
        "decision": "SHARIA_REJECTED",
        "buy_allowed": False,
        "rejection_reason": reason,
        "rejection_code": rejection_code,
        "zoya_status": (zoya or {}).get("status", "UNKNOWN"),
        "zoya_purification": (zoya or {}).get("purification", None),
        "fltrna_purification": (fltrna or {}).get("purification", None),
        "sources_agree": False,
        "cached": False,
    }


def _buy_allowed(ticker: str, zoya: dict, fltrna: dict) -> dict:
    return {
        "ticker": ticker,
        "decision": "BUY_ALLOWED",
        "buy_allowed": True,
        "rejection_reason": "",
        "rejection_code": "",
        "zoya_status": zoya["status"],
        "zoya_purification": zoya["purification"],
        "fltrna_purification": fltrna["purification"],
        "sources_agree": True,
        "cached": False,
    }


class UltraStrictShariaFilter:
    """
    فلتر شرعي فائق الصرامة.

    يُسمح بالشراء (BUY_ALLOWED) فقط عند:
      - Zoya status = COMPLIANT
      - Zoya purification = 0%
      - Fltrna purification = 0%
      - كلا المصدرين أعطيا بيانات
      - لا تعارض بينهما

    أي شرط مفقود → SHARIA_REJECTED.
    """

    CACHE_DIR = Path("cache/ultra_strict")
    CACHE_TTL_HOURS = 24

    ZOYA_ENDPOINT = "https://api.zoya.finance/graphql"
    ZOYA_SANDBOX_ENDPOINT = "https://sandbox-api.zoya.finance/graphql"

    def __init__(
        self,
        zoya_api_key: str = "",
        fltrna_api_key: str = "",
        zoya_sandbox: bool = False,
    ):
        if not zoya_api_key:
            raise ValueError("Zoya API key is required for UltraStrictShariaFilter")
        if not fltrna_api_key:
            raise ValueError("Fltrna API key is required for UltraStrictShariaFilter")

        self.zoya_key = zoya_api_key
        self.fltrna_key = fltrna_api_key
        self._zoya_endpoint = (
            self.ZOYA_SANDBOX_ENDPOINT if zoya_sandbox else self.ZOYA_ENDPOINT
        )
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "FalconAICapital/1.0 UltraStrictFilter",
            "Accept": "application/json",
        })

    # ── نقطة الدخول الرئيسية ──────────────────────────────────────────────────

    def check(self, ticker: str) -> dict:
        """
        يتحقق من السهم ويُرجع BUY_ALLOWED أو SHARIA_REJECTED.

        Returns:
          {
            "ticker":             "PANW",
            "decision":           "BUY_ALLOWED" | "SHARIA_REJECTED",
            "buy_allowed":        True | False,
            "rejection_reason":   "",                 ← فارغ إذا BUY_ALLOWED
            "rejection_code":     "",
            "zoya_status":        "COMPLIANT",
            "zoya_purification":  0.0,
            "fltrna_purification": 0.0,
            "sources_agree":      True,
            "cached":             False,
          }
        """
        ticker = ticker.upper().strip()

        cached = self._load_cache(ticker)
        if cached:
            cached["cached"] = True
            return cached

        result = self._run_ultra_strict_check(ticker)
        self._save_cache(ticker, result)
        return result

    def check_list(self, tickers: list[str]) -> dict[str, dict]:
        """يفحص قائمة أسهم — يُرجع dict {ticker: result}."""
        results = {}
        for ticker in tickers:
            results[ticker] = self.check(ticker)
            status = results[ticker]["decision"]
            logger.info(f"{ticker}: {status}")
        return results

    def filter_buy_allowed(self, tickers: list[str]) -> list[str]:
        """يُرجع فقط الأسهم المسموح بشرائها (BUY_ALLOWED)."""
        return [
            t for t, r in self.check_list(tickers).items()
            if r["buy_allowed"]
        ]

    # ── المنطق الأساسي ────────────────────────────────────────────────────────

    def _run_ultra_strict_check(self, ticker: str) -> dict:
        # ① رفض فوري من القائمة المحلية
        if ticker in KNOWN_HARAM:
            return _sharia_rejected(
                ticker,
                reason="سهم محظور شرعاً (بنوك/خمور/قمار/تأمين/أسلحة)",
                rejection_code="KNOWN_HARAM",
            )

        if ticker in HALAL_WITH_PURIFICATION:
            return _sharia_rejected(
                ticker,
                reason="السهم حلال لكن به نسبة تطهير — مرفوض بالفلتر الصارم",
                rejection_code="HAS_PURIFICATION",
            )

        # ② جلب بيانات Zoya (إلزامي)
        zoya = self._fetch_zoya(ticker)
        if zoya is None:
            return _sharia_rejected(
                ticker,
                reason="تعذّر الحصول على بيانات Zoya — مرفوض احتياطاً",
                rejection_code="ZOYA_DATA_MISSING",
            )

        # ③ Zoya يجب أن تكون COMPLIANT
        if zoya["status"] != "COMPLIANT":
            return _sharia_rejected(
                ticker,
                reason=f"Zoya: الحالة الشرعية = {zoya['status']} (غير COMPLIANT)",
                rejection_code="ZOYA_NOT_COMPLIANT",
                zoya=zoya,
            )

        # ④ Zoya purification يجب أن تكون 0%
        if zoya["purification"] > _PURIFICATION_TOLERANCE:
            return _sharia_rejected(
                ticker,
                reason=f"Zoya: نسبة التطهير = {zoya['purification']}% > 0%",
                rejection_code="ZOYA_PURIFICATION_NONZERO",
                zoya=zoya,
            )

        # ⑤ جلب بيانات Fltrna (إلزامي)
        fltrna = self._fetch_fltrna(ticker)
        if fltrna is None:
            return _sharia_rejected(
                ticker,
                reason="تعذّر الحصول على بيانات Fltrna — مرفوض احتياطاً",
                rejection_code="FLTRNA_DATA_MISSING",
                zoya=zoya,
            )

        # ⑥ Fltrna purification يجب أن تكون 0%
        if fltrna["purification"] > _PURIFICATION_TOLERANCE:
            return _sharia_rejected(
                ticker,
                reason=f"Fltrna: نسبة التطهير = {fltrna['purification']}% > 0%",
                rejection_code="FLTRNA_PURIFICATION_NONZERO",
                zoya=zoya,
                fltrna=fltrna,
            )

        # ⑦ التحقق من توافق المصدرين
        disagreement = self._detect_disagreement(zoya, fltrna)
        if disagreement:
            return _sharia_rejected(
                ticker,
                reason=f"تعارض بين المصدرين: {disagreement}",
                rejection_code="SOURCE_DISAGREEMENT",
                zoya=zoya,
                fltrna=fltrna,
            )

        # ✅ جميع الشروط متحققة
        return _buy_allowed(ticker, zoya, fltrna)

    # ── Zoya Finance API ──────────────────────────────────────────────────────

    def _fetch_zoya(self, ticker: str) -> Optional[dict]:
        """
        يجلب الحالة الشرعية ونسبة التطهير من Zoya Finance.
        يُرجع None عند أي فشل.
        مفتاح مجاني: https://zoya.finance
        """
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
        try:
            resp = self._session.post(
                self._zoya_endpoint,
                json={"query": query, "variables": {"ticker": ticker}},
                headers={"Authorization": f"Bearer {self.zoya_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {}).get("stockReport") or {}
            if not data:
                logger.warning(f"Zoya: no stockReport data for {ticker}")
                return None

            status = str(data.get("complianceStatus") or "").upper()
            # purificationRatio من Zoya: نسبة 0.0–1.0 → نحوّلها لمئوية
            ratio_raw = data.get("purificationRatio")
            if ratio_raw is None:
                logger.warning(f"Zoya: purificationRatio missing for {ticker}")
                return None

            purification = round(float(ratio_raw) * 100, 4)
            return {
                "status": status,
                "purification": purification,
                "sector": data.get("businessSector", ""),
            }
        except Exception as e:
            logger.error(f"Zoya API error for {ticker}: {e}")
            return None

    # ── Fltrna API ────────────────────────────────────────────────────────────

    def _fetch_fltrna(self, ticker: str) -> Optional[dict]:
        """
        يجلب نسبة التطهير من Fltrna.
        يُرجع None عند أي فشل أو بيانات مفقودة.
        مفتاح: https://fltrna.com
        """
        try:
            resp = self._session.get(
                f"https://api.fltrna.com/v1/stocks/{ticker}",
                headers={"X-API-Key": self.fltrna_key},
                timeout=10,
            )
            if resp.status_code == 404:
                logger.warning(f"Fltrna: {ticker} not found (404)")
                return None
            if resp.status_code in (401, 403):
                logger.error(f"Fltrna: authentication failed (status {resp.status_code})")
                return None
            resp.raise_for_status()
            data = resp.json()

            # Fltrna قد تُعيد purificationRatio أو purificationPercentage
            ratio_raw = None
            for _key in ("purificationRatio", "purificationPercentage",
                         "purification_ratio", "purification_percentage"):
                if _key in data:
                    ratio_raw = data[_key]
                    break
            if ratio_raw is None:
                logger.warning(f"Fltrna: purification field missing for {ticker}")
                return None

            purification = _parse_purification(str(ratio_raw))
            return {"purification": purification}

        except Exception as e:
            logger.error(f"Fltrna API error for {ticker}: {e}")
            return None

    # ── كشف التعارض ──────────────────────────────────────────────────────────

    @staticmethod
    def _detect_disagreement(zoya: dict, fltrna: dict) -> str:
        """
        يكشف تعارضاً جوهرياً بين المصدرين.
        كلاهما 0% = لا تعارض.
        اختلاف > 0 = تعارض.
        يُرجع رسالة التعارض أو "" إذا لا تعارض.
        """
        z_p = zoya["purification"]
        f_p = fltrna["purification"]
        if abs(z_p - f_p) > _PURIFICATION_TOLERANCE:
            return (
                f"Zoya purification={z_p}% ≠ Fltrna purification={f_p}%"
            )
        return ""

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _load_cache(self, ticker: str) -> Optional[dict]:
        path = self.CACHE_DIR / f"{ticker}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
            if datetime.now() - cached_at > timedelta(hours=self.CACHE_TTL_HOURS):
                return None
            return data
        except Exception:
            return None

    def _save_cache(self, ticker: str, result: dict):
        path = self.CACHE_DIR / f"{ticker}.json"
        path.write_text(json.dumps(
            {**result, "_cached_at": datetime.now().isoformat()},
            ensure_ascii=False, indent=2,
        ))


# ── أداة مساعدة مشتركة ───────────────────────────────────────────────────────

def _parse_purification(value: str) -> float:
    """يحوّل نسبة التطهير: '0%', '1.5٪', '0.015' → float مئوي."""
    cleaned = (
        value.replace("%", "").replace("٪", "")
             .replace("،", ".").replace(",", ".")
             .strip()
    )
    try:
        num = float(cleaned)
        # إذا كانت النسبة عشرية (0.015) نحوّلها لمئوية (1.5)
        if 0 < num < 1:
            num = num * 100
        return round(num, 4)
    except ValueError:
        return 0.0
