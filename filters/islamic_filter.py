"""
Islamic Stock Filter — Falcon AI Capital
Sources priority:
  1. Zoya Finance API   (US stocks - best for Alpaca)
  2. Musaffa API        (US + Global)
  3. Al-Rajhi Capital   (Saudi stocks — scrape published list)
  4. Al-Bilad Capital   (Saudi stocks — scrape published list)
  5. Local cache        (avoid repeated calls)

شرط القبول:
  ✅ الحالة الشرعية: COMPLIANT
  ✅ نسبة التطهير:   0.0% بالضبط
  ❌ أي نسبة تطهير > 0% = مرفوض (مثل AAPL, NVDA فيها تطهير)
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── قطاعات محظورة ─────────────────────────────────────────────────────────────
FORBIDDEN_SECTORS = {
    "alcohol", "tobacco", "gambling", "gaming", "weapons", "defense",
    "conventional banking", "conventional finance", "insurance",
    "pork", "adult entertainment", "pornography", "cannabis", "marijuana",
    "interest-based lending", "riba",
}

# ── أسهم حلال بتطهير صفر — من ETF إسلامية مشددة (SPUS فئة صفر تطهير) ────────
# هذه القائمة للتحقق السريع فقط — الAPI يُثبّتها
# AAPL, NVDA, MSFT, GOOGL مستبعدة لأن فيها نسبة تطهير > 0%
LIKELY_HALAL_ZERO = {
    # تكنولوجيا خالصة بدون فوائد بنكية تذكر
    "PANW", "CRWD", "FTNT", "ZS", "OKTA",       # أمن سيبراني
    "ANSS", "SNPS", "CDNS", "PTC",               # برامج هندسية
    "EPAM", "GLOB", "FLUT",                       # خدمات تقنية
    # رعاية صحية
    "IDXX", "HOLX", "PODD", "INSP",
    # صناعية
    "ROK", "NOVT", "ESAB",
    # طاقة متجددة
    "NEE", "BEP", "CWEN",
}

# ── أسهم حلال لكن بتطهير — نرفضها تلقائياً ────────────────────────────────────
# (للمعلومية فقط — البوت لا يتداولها)
HALAL_WITH_PURIFICATION = {
    "AAPL",   # ~1.5% تطهير (دخل فوائد من الكاش)
    "NVDA",   # ~1.0% تطهير
    "MSFT",   # ~1.2% تطهير
    "GOOGL", "GOOG",  # ~0.8% تطهير
    "AMZN",   # ~0.5% تطهير
    "META",   # ~0.4% تطهير
    "TSLA",   # ~0.3% تطهير
    "AMGN", "GILD",   # فوائد بنكية
}

# ── أسهم حرام — رفض فوري ─────────────────────────────────────────────────────
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


class IslamicFilter:

    CACHE_DIR = Path("cache/islamic")
    CACHE_TTL_HOURS = 24

    def __init__(self, zoya_api_key: str = "", musaffa_api_key: str = ""):
        self.zoya_key = zoya_api_key
        self.musaffa_key = musaffa_api_key
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "FalconAICapital/1.0 (Islamic trading bot)",
            "Accept": "application/json",
        })

    # ── نقطة الدخول الرئيسية ──────────────────────────────────────────────────

    def is_halal(self, ticker: str, exchange: str = "US") -> dict:
        """
        Returns:
          {
            "ticker":            "PANW",
            "halal":             True,
            "purification_rate": 0.0,       ← يجب أن تكون 0.0 بالضبط
            "status":            "COMPLIANT",
            "source":            "zoya",
            "sector":            "Technology",
            "reason":            "",
            "cached":            False,
          }

        شرط القبول: COMPLIANT + purification_rate == 0.0
        """
        ticker = ticker.upper().strip()

        cached = self._load_cache(ticker)
        if cached:
            cached["cached"] = True
            return cached

        # رفض فوري للحرام
        if ticker in KNOWN_HARAM:
            result = self._reject(ticker, "known_haram_list", "سهم محظور (بنوك/خمور/قمار/تأمين)")

        # رفض فوري لحلال بتطهير
        elif ticker in HALAL_WITH_PURIFICATION:
            result = self._reject(
                ticker, "halal_with_purification",
                f"حلال لكن فيه نسبة تطهير — غير مسموح بتداوله"
            )

        # تحقق كامل من APIs
        else:
            api_result = self._check_all_sources(ticker, exchange)
            if api_result is None:
                # مجهول ولا يوجد بيانات — رفض احتياطاً
                result = self._reject(ticker, "no_data", "لا توجد بيانات كافية — مرفوض احتياطاً")
            else:
                result = api_result

        self._save_cache(ticker, result)
        result["cached"] = False
        return result

    def filter_list(self, tickers: list[str], exchange: str = "US") -> list[str]:
        """يرجع الأسهم الحلال بنسبة تطهير 0% فقط."""
        approved = []
        for ticker in tickers:
            result = self.is_halal(ticker, exchange)
            if result["halal"]:
                approved.append(ticker)
            else:
                logger.info(
                    f"Rejected {ticker} | "
                    f"rate={result['purification_rate']}% | "
                    f"{result.get('reason', '')}"
                )
        return approved

    # ── المصدر 1: Zoya Finance ────────────────────────────────────────────────

    def _check_zoya(self, ticker: str) -> Optional[dict]:
        """
        أفضل مصدر للأسهم الأمريكية.
        مفتاح مجاني: https://zoya.finance
        """
        if not self.zoya_key:
            return None
        try:
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
            resp = self._session.post(
                "https://api.zoya.finance/graphql",
                json={"query": query, "variables": {"ticker": ticker}},
                headers={"Authorization": f"Bearer {self.zoya_key}"},
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {}).get("stockReport", {})
            if not data:
                return None

            status = data.get("complianceStatus", "")
            # purificationRatio: 0.0–1.0 → نسبة مئوية
            purification = round(float(data.get("purificationRatio") or 0) * 100, 4)
            halal = status == "COMPLIANT" and purification == 0.0

            reason = ""
            if not halal:
                if status != "COMPLIANT":
                    reason = f"Zoya: {status}"
                else:
                    reason = f"نسبة تطهير {purification}% > 0%"

            return {
                "ticker": ticker,
                "halal": halal,
                "purification_rate": purification,
                "status": status,
                "source": "zoya",
                "sector": data.get("businessSector", ""),
                "reason": reason,
            }
        except Exception as e:
            logger.warning(f"Zoya check failed for {ticker}: {e}")
            return None

    # ── المصدر 2: Musaffa ─────────────────────────────────────────────────────

    def _check_musaffa(self, ticker: str) -> Optional[dict]:
        """
        يغطي أسهم عالمية.
        مفتاح مجاني: https://musaffa.com
        """
        try:
            url = f"https://api.musaffa.com/v1/stocks/{ticker}/compliance"
            headers = {"X-API-Key": self.musaffa_key} if self.musaffa_key else {}
            resp = self._session.get(url, headers=headers, timeout=8)
            if resp.status_code in (401, 403, 404):
                return None
            resp.raise_for_status()
            data = resp.json()

            compliance = data.get("complianceStatus", "")
            purification = round(float(data.get("purificationPercentage") or 0), 4)
            halal = compliance == "COMPLIANT" and purification == 0.0

            reason = ""
            if not halal:
                if compliance != "COMPLIANT":
                    reason = f"Musaffa: {compliance}"
                else:
                    reason = f"نسبة تطهير {purification}% > 0%"

            return {
                "ticker": ticker,
                "halal": halal,
                "purification_rate": purification,
                "status": compliance,
                "source": "musaffa",
                "sector": data.get("sector", ""),
                "reason": reason,
            }
        except Exception as e:
            logger.warning(f"Musaffa check failed for {ticker}: {e}")
            return None

    # ── المصدر 3: الراجحي كابيتال ────────────────────────────────────────────

    def _check_alrajhi(self, ticker: str) -> Optional[dict]:
        """
        الراجحي كابيتال — للأسهم السعودية.
        الأعمدة: رمز | اسم | الحالة الشرعية | نسبة التطهير
        """
        try:
            url = "https://www.alrajhicapital.com.sa/ar/investment-tools/shariah-screening"
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            clean = ticker.replace(".SR", "").strip()
            for row in soup.select("table tbody tr"):
                cols = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cols) >= 3 and cols[0].replace(".SR", "").strip() == clean:
                    status_ar = cols[2] if len(cols) > 2 else ""
                    purification = self._parse_purification(cols[3] if len(cols) > 3 else "0")
                    is_compliant = "متوافق" in status_ar or "مباح" in status_ar
                    halal = is_compliant and purification == 0.0

                    reason = ""
                    if not halal:
                        if not is_compliant:
                            reason = f"الراجحي: {status_ar}"
                        else:
                            reason = f"نسبة تطهير {purification}% > 0%"

                    return {
                        "ticker": ticker,
                        "halal": halal,
                        "purification_rate": purification,
                        "status": "COMPLIANT" if is_compliant else "NON_COMPLIANT",
                        "source": "alrajhi_capital",
                        "sector": cols[1] if len(cols) > 1 else "",
                        "reason": reason,
                    }
            return None
        except Exception as e:
            logger.warning(f"Al-Rajhi check failed for {ticker}: {e}")
            return None

    # ── المصدر 4: البلاد كابيتال ─────────────────────────────────────────────

    def _check_albilad(self, ticker: str) -> Optional[dict]:
        """
        البلاد كابيتال — للأسهم السعودية.
        الأعمدة: رمز | اسم | الحالة | نسبة التطهير
        """
        try:
            url = "https://www.albilad-capital.com/ar/tools/shariah"
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            clean = ticker.replace(".SR", "").strip()
            for row in soup.select("table tbody tr"):
                cols = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cols) >= 2 and cols[0].replace(".SR", "").strip() == clean:
                    status_ar = cols[2] if len(cols) > 2 else ""
                    purification = self._parse_purification(cols[3] if len(cols) > 3 else "0")
                    is_compliant = "متوافق" in status_ar or "حلال" in status_ar
                    halal = is_compliant and purification == 0.0

                    reason = ""
                    if not halal:
                        if not is_compliant:
                            reason = f"البلاد: {status_ar}"
                        else:
                            reason = f"نسبة تطهير {purification}% > 0%"

                    return {
                        "ticker": ticker,
                        "halal": halal,
                        "purification_rate": purification,
                        "status": "COMPLIANT" if is_compliant else "NON_COMPLIANT",
                        "source": "albilad_capital",
                        "sector": "",
                        "reason": reason,
                    }
            return None
        except Exception as e:
            logger.warning(f"Al-Bilad check failed for {ticker}: {e}")
            return None

    # ── فحص القطاع (احتياطي) ─────────────────────────────────────────────────

    def _check_sector(self, ticker: str) -> Optional[dict]:
        """يرفض القطاعات المحظورة — لا يُثبت التطهير صفر."""
        try:
            resp = self._session.get(
                f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}",
                params={"modules": "assetProfile"},
                timeout=6,
            )
            profile = (
                resp.json()
                    .get("quoteSummary", {})
                    .get("result", [{}])[0]
                    .get("assetProfile", {})
            )
            sector = (profile.get("sector") or "").lower()
            industry = (profile.get("industry") or "").lower()

            for forbidden in FORBIDDEN_SECTORS:
                if forbidden in sector + " " + industry:
                    return self._reject(ticker, "sector_check", f"قطاع محظور: {sector}")

            # يبدو مسموحاً من ناحية القطاع — لكن لم نتحقق من التطهير
            # نرجع None لأننا غير متأكدين من نسبة التطهير
            logger.info(f"{ticker}: القطاع مسموح ({sector}) — يحتاج Zoya/Musaffa للتثبت")
            return None
        except Exception as e:
            logger.warning(f"Sector check failed for {ticker}: {e}")
            return None

    # ── تنسيق المصادر ─────────────────────────────────────────────────────────

    def _check_all_sources(self, ticker: str, exchange: str) -> Optional[dict]:
        """يجرب المصادر بالترتيب. يرجع None إذا لم يتحقق أحد."""
        is_saudi = exchange in ("SR", "TADAWUL") or ticker.endswith(".SR")

        if is_saudi:
            api_sources = [self._check_alrajhi, self._check_albilad,
                           self._check_zoya, self._check_musaffa]
        else:
            api_sources = [self._check_zoya, self._check_musaffa]

        for checker in api_sources:
            result = checker(ticker)
            if result is not None:
                return result

        # آخر ملجأ: فحص القطاع (لا يُثبت التطهير)
        return self._check_sector(ticker)

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
            ensure_ascii=False, indent=2
        ))

    # ── أدوات مساعدة ─────────────────────────────────────────────────────────

    @staticmethod
    def _reject(ticker: str, source: str, reason: str) -> dict:
        return {
            "ticker": ticker,
            "halal": False,
            "purification_rate": 0.0,
            "status": "NON_COMPLIANT",
            "source": source,
            "sector": "",
            "reason": reason,
        }

    @staticmethod
    def _parse_purification(value: str) -> float:
        """يحوّل نسبة التطهير: '0%', '1.5٪', '0.015' → float."""
        cleaned = (
            value.replace("%", "").replace("٪", "")
                 .replace("،", ".").replace(",", ".")
                 .strip()
        )
        try:
            num = float(cleaned)
            if 0 < num < 1:
                num = num * 100
            return round(num, 4)
        except ValueError:
            return 0.0
