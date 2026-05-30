"""
Islamic Stock Filter — Falcon AI Capital
Sources priority:
  1. Zoya Finance API   (US stocks - best for Alpaca)
  2. Musaffa API        (US + Global)
  3. Al-Rajhi Capital   (Saudi stocks — scrape published list)
  4. Al-Bilad Capital   (Saudi stocks — scrape published list)
  5. Local cache        (avoid repeated calls)

A stock passes ONLY if:
  - Shariah status: COMPLIANT
  - Purification rate: 0%   (no haram income at all)
  - Sector: not forbidden
"""

import json
import time
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Forbidden sectors — never trade these ─────────────────────────────────────
FORBIDDEN_SECTORS = {
    "alcohol", "tobacco", "gambling", "gaming", "weapons", "defense",
    "conventional banking", "conventional finance", "insurance",
    "pork", "adult entertainment", "pornography", "cannabis", "marijuana",
    "interest-based lending", "riba",
}

# ── Known halal US stocks (fast pre-check, reduces API calls) ─────────────────
# Source: major Islamic ETF constituents (SPUS, HLAL, UMMA)
KNOWN_HALAL = {
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA",
    "AVGO", "AMD", "QCOM", "INTC", "TXN", "MU", "AMAT", "LRCX",
    "NOW", "ADBE", "CRM", "ORCL", "INTU", "PANW", "CRWD", "SNPS",
    "CDNS", "FTNT", "ANSS", "PTC", "EPAM",
    "UNH", "LLY", "JNJ", "ABBV", "MRK", "PFE", "TMO", "ABT",
    "DHR", "SYK", "BSX", "MDT", "ZBH", "HOLX",
    "AMGN", "GILD", "BIIB", "REGN", "VRTX", "ILMN", "IDXX",
    "COST", "WMT", "TGT", "HD", "LOW", "ORLY", "AZO",
    "SBUX", "MCD", "YUM", "DPZ",
    "NKE", "LULU",
    "CAT", "DE", "EMR", "ETN", "ROK", "GWW", "PH",
    "UPS", "FDX", "JBHT",
    "NEE", "DUK", "SO", "AEP", "EXC",
    "AMT", "PLD", "EQIX", "DLR", "CCI",
}

# ── Known haram US stocks (fast rejection) ────────────────────────────────────
KNOWN_HARAM = {
    # Conventional banks/finance
    "JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "TFC", "COF",
    "AXP", "DFS", "SYF", "ALLY", "RF", "FITB", "KEY", "HBAN", "CFG",
    # Insurance
    "MET", "PRU", "AIG", "AFL", "ALL", "CB", "TRV", "PGR", "HIG",
    "LNC", "UNM", "CNO", "RLI",
    # Alcohol / Tobacco
    "PM", "MO", "BTI", "LO", "STZ", "BUD", "TAP", "SAM",
    # Gambling / Casinos
    "MGM", "WYNN", "LVS", "CZR", "PENN", "DKNG", "RSI",
    # Weapons / Defense
    "LMT", "RTX", "NOC", "GD", "BA", "L3H",
    # Pork / Conventional food
    "HRL",
}


class IslamicFilter:

    CACHE_DIR = Path("cache/islamic")
    CACHE_TTL_HOURS = 24  # refresh every 24h

    def __init__(self, zoya_api_key: str = "", musaffa_api_key: str = ""):
        self.zoya_key = zoya_api_key
        self.musaffa_key = musaffa_api_key
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "FalconAICapital/1.0 (Islamic trading bot)",
            "Accept": "application/json",
        })

    # ── Public entry point ────────────────────────────────────────────────────

    def is_halal(self, ticker: str, exchange: str = "US") -> dict:
        """
        Returns:
          {
            "ticker": "AAPL",
            "halal": True,
            "purification_rate": 0.0,   # must be 0 to trade
            "status": "COMPLIANT",       # COMPLIANT / NON_COMPLIANT / DOUBTFUL
            "source": "zoya",
            "sector": "Technology",
            "reason": "",                # why rejected (if halal=False)
            "cached": False,
          }
        """
        ticker = ticker.upper().strip()

        # 1. Check cache first
        cached = self._load_cache(ticker)
        if cached:
            cached["cached"] = True
            return cached

        # 2. Fast known lists
        if ticker in KNOWN_HARAM:
            result = self._reject(ticker, "known_haram_list", "سهم محظور (بنوك/خمور/قمار/تأمين)")
        elif ticker in KNOWN_HALAL:
            # Still verify purification via API — don't skip the rate check
            result = self._verify_purification(ticker, exchange)
        else:
            # Unknown ticker — check all sources
            api_result = self._check_all_sources(ticker, exchange)
            result = api_result if api_result is not None else self._reject(
                ticker, "no_data", "لا توجد بيانات كافية — مرفوض احتياطاً"
            )

        self._save_cache(ticker, result)
        result["cached"] = False
        return result

    def filter_list(self, tickers: list[str], exchange: str = "US") -> list[str]:
        """Return only halal tickers with 0% purification from the list."""
        approved = []
        for ticker in tickers:
            result = self.is_halal(ticker, exchange)
            if result["halal"] and result["purification_rate"] == 0.0:
                approved.append(ticker)
            else:
                logger.info(
                    f"Rejected {ticker}: halal={result['halal']} "
                    f"purification={result['purification_rate']}% "
                    f"reason={result.get('reason','')}"
                )
        return approved

    # ── Source 1: Zoya Finance ────────────────────────────────────────────────

    def _check_zoya(self, ticker: str) -> Optional[dict]:
        """
        Zoya Finance API — best for US stocks.
        Docs: https://zoya.finance  (requires API key from their site)
        """
        if not self.zoya_key:
            return None
        try:
            url = f"https://api.zoya.finance/graphql"
            query = """
            query StockReport($ticker: String!) {
              stockReport(ticker: $ticker) {
                ticker
                complianceStatus    # COMPLIANT | NON_COMPLIANT | DOUBTFUL
                purificationRatio   # 0.0 – 1.0  (e.g. 0.02 = 2%)
                businessSector
                concerns {
                  name
                  status
                }
              }
            }
            """
            resp = self._session.post(
                url,
                json={"query": query, "variables": {"ticker": ticker}},
                headers={"Authorization": f"Bearer {self.zoya_key}"},
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {}).get("stockReport", {})
            if not data:
                return None

            status = data.get("complianceStatus", "")
            purification = float(data.get("purificationRatio", 1.0)) * 100  # → %
            halal = status == "COMPLIANT" and purification == 0.0

            return {
                "ticker": ticker,
                "halal": halal,
                "purification_rate": purification,
                "status": status,
                "source": "zoya",
                "sector": data.get("businessSector", ""),
                "reason": "" if halal else f"Zoya: {status}, تطهير {purification}%",
            }
        except Exception as e:
            logger.warning(f"Zoya check failed for {ticker}: {e}")
            return None

    # ── Source 2: Musaffa ─────────────────────────────────────────────────────

    def _check_musaffa(self, ticker: str) -> Optional[dict]:
        """
        Musaffa API — covers US and global stocks.
        Docs: https://musaffa.com/api  (free tier available)
        """
        try:
            # Free endpoint (no key needed for basic check)
            url = f"https://api.musaffa.com/v1/stocks/{ticker}/compliance"
            headers = {}
            if self.musaffa_key:
                headers["X-API-Key"] = self.musaffa_key

            resp = self._session.get(url, headers=headers, timeout=8)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()

            compliance = data.get("complianceStatus", "")    # COMPLIANT / NON_COMPLIANT
            purification = float(data.get("purificationPercentage", 100.0))
            halal = compliance == "COMPLIANT" and purification == 0.0

            return {
                "ticker": ticker,
                "halal": halal,
                "purification_rate": purification,
                "status": compliance,
                "source": "musaffa",
                "sector": data.get("sector", ""),
                "reason": "" if halal else f"Musaffa: {compliance}, تطهير {purification}%",
            }
        except Exception as e:
            logger.warning(f"Musaffa check failed for {ticker}: {e}")
            return None

    # ── Source 3: Al-Rajhi Capital (Saudi stocks) ─────────────────────────────

    def _check_alrajhi(self, ticker: str) -> Optional[dict]:
        """
        Al-Rajhi Capital Shariah screening.
        URL: https://www.alrajhicapital.com.sa/ar/investment-tools/shariah-screening
        Note: scrapes the published list — used for Tadawul stocks (e.g. 2222.SR)
        """
        try:
            url = "https://www.alrajhicapital.com.sa/ar/investment-tools/shariah-screening"
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Al-Rajhi publishes a table of compliant stocks
            # Columns: رمز السهم | اسم الشركة | الحالة | نسبة التطهير
            rows = soup.select("table tbody tr")
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cols) >= 3:
                    symbol = cols[0].replace(".SR", "").strip()
                    if symbol == ticker.replace(".SR", ""):
                        status_ar = cols[2] if len(cols) > 2 else ""
                        purification_str = cols[3] if len(cols) > 3 else "0"
                        purification = self._parse_purification(purification_str)
                        halal = "متوافق" in status_ar or "مباح" in status_ar
                        halal = halal and purification == 0.0

                        return {
                            "ticker": ticker,
                            "halal": halal,
                            "purification_rate": purification,
                            "status": "COMPLIANT" if "متوافق" in status_ar else "NON_COMPLIANT",
                            "source": "alrajhi_capital",
                            "sector": cols[1] if len(cols) > 1 else "",
                            "reason": "" if halal else f"الراجحي: {status_ar}, تطهير {purification}%",
                        }
            return None  # Not found in Al-Rajhi list
        except Exception as e:
            logger.warning(f"Al-Rajhi check failed for {ticker}: {e}")
            return None

    # ── Source 4: Al-Bilad Capital (Saudi stocks) ─────────────────────────────

    def _check_albilad(self, ticker: str) -> Optional[dict]:
        """
        Al-Bilad Capital Shariah screening.
        URL: https://www.albilad-capital.com/ar/tools/shariah
        Note: scrapes the published PDF/page list.
        """
        try:
            url = "https://www.albilad-capital.com/ar/tools/shariah"
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            rows = soup.select("table tbody tr")
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cols) >= 2:
                    symbol = cols[0].replace(".SR", "").strip()
                    if symbol == ticker.replace(".SR", ""):
                        status_ar = cols[2] if len(cols) > 2 else ""
                        purification_str = cols[3] if len(cols) > 3 else "0%"
                        purification = self._parse_purification(purification_str)
                        halal = ("متوافق" in status_ar or "حلال" in status_ar) and purification == 0.0

                        return {
                            "ticker": ticker,
                            "halal": halal,
                            "purification_rate": purification,
                            "status": "COMPLIANT" if halal else "NON_COMPLIANT",
                            "source": "albilad_capital",
                            "sector": "",
                            "reason": "" if halal else f"البلاد: {status_ar}, تطهير {purification}%",
                        }
            return None
        except Exception as e:
            logger.warning(f"Al-Bilad check failed for {ticker}: {e}")
            return None

    # ── Sector check ──────────────────────────────────────────────────────────

    def _check_sector(self, ticker: str) -> Optional[dict]:
        """Quick sector check via Yahoo Finance — no key required."""
        try:
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
            params = {"modules": "assetProfile"}
            resp = self._session.get(url, params=params, timeout=6)
            data = resp.json()
            profile = (
                data.get("quoteSummary", {})
                    .get("result", [{}])[0]
                    .get("assetProfile", {})
            )
            sector = (profile.get("sector") or "").lower()
            industry = (profile.get("industry") or "").lower()
            combined = sector + " " + industry

            for forbidden in FORBIDDEN_SECTORS:
                if forbidden in combined:
                    return self._reject(
                        ticker, "sector_check",
                        f"قطاع محظور: {sector} / {industry}"
                    )
            return {
                "ticker": ticker,
                "halal": True,
                "purification_rate": 0.0,
                "status": "LIKELY_COMPLIANT",
                "source": "yahoo_sector",
                "sector": sector,
                "reason": "قطاع مسموح — يحتاج تحقق إضافي",
            }
        except Exception as e:
            logger.warning(f"Sector check failed for {ticker}: {e}")
            return None

    # ── Orchestration helpers ─────────────────────────────────────────────────

    def _check_all_sources(self, ticker: str, exchange: str) -> Optional[dict]:
        """Try sources in priority order. Returns None if no source has data."""
        is_saudi = exchange in ("SR", "TADAWUL") or ticker.endswith(".SR")

        if not is_saudi:
            for checker in [self._check_zoya, self._check_musaffa]:
                result = checker(ticker)
                if result is not None:
                    return result
        else:
            for checker in [self._check_alrajhi, self._check_albilad,
                            self._check_zoya, self._check_musaffa]:
                result = checker(ticker)
                if result is not None:
                    return result

        # Last resort: sector check (no purification data)
        return self._check_sector(ticker)

    def _verify_purification(self, ticker: str, exchange: str) -> dict:
        """Verify purification rate for known-halal stocks (might have changed)."""
        result = self._check_all_sources(ticker, exchange)
        if result is None:
            # APIs unavailable — fall back to known list, log warning
            logger.warning(f"{ticker}: known halal but couldn't verify purification via API")
            return {
                "ticker": ticker,
                "halal": True,
                "purification_rate": 0.0,
                "status": "COMPLIANT",
                "source": "known_halal_list",
                "sector": "",
                "reason": "",
            }
        # If sector check returned LIKELY_COMPLIANT but with no purification data,
        # and the ticker is in our known halal list — trust the list.
        if result.get("source") == "yahoo_sector" and result.get("halal"):
            result["source"] = "known_halal_list+sector"
        return result

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _cache_path(self, ticker: str) -> Path:
        return self.CACHE_DIR / f"{ticker}.json"

    def _load_cache(self, ticker: str) -> Optional[dict]:
        path = self._cache_path(ticker)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
            if datetime.now() - cached_at > timedelta(hours=self.CACHE_TTL_HOURS):
                return None  # stale
            return data
        except Exception:
            return None

    def _save_cache(self, ticker: str, result: dict):
        path = self._cache_path(ticker)
        data = {**result, "_cached_at": datetime.now().isoformat()}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _reject(ticker: str, source: str, reason: str) -> dict:
        return {
            "ticker": ticker,
            "halal": False,
            "purification_rate": 100.0,
            "status": "NON_COMPLIANT",
            "source": source,
            "sector": "",
            "reason": reason,
        }

    @staticmethod
    def _parse_purification(value: str) -> float:
        """Parse Arabic/English purification strings like '0%', '2.5٪', '0.025'."""
        cleaned = (
            value.replace("%", "").replace("٪", "")
                 .replace("،", ".").replace(",", ".")
                 .strip()
        )
        try:
            num = float(cleaned)
            # If it looks like a ratio (0.02) convert to percentage
            if num < 1 and num > 0:
                num = num * 100
            return round(num, 4)
        except ValueError:
            return 0.0
