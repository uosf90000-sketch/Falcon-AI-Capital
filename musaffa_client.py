"""
Musaffa Client — يسحب بيانات الحلال من موقع musaffa.com
بدون API key — يقرأ صفحة السهم مباشرة.
"""

import os
import re
import json
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

CACHE_DIR = Path("cache/musaffa")
CACHE_TTL  = timedelta(hours=24)


class MusaffaClient:

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
    }

    def __init__(self, api_key: str = ""):
        # api_key اختياري — إذا عندك استخدمه، وإلا scraping
        self.api_key = api_key or os.getenv("MUSAFFA_API_KEY", "")
        self._session = requests.Session()
        self._session.headers.update(self.HEADERS)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ── نقطة الدخول الرئيسية ─────────────────────────────────────────────────

    def is_halal_zero(self, ticker: str) -> dict:
        """
        يرجع:
          halal=True  فقط إذا COMPLIANT + purification == 0.0
          halal=False في أي حالة أخرى
        """
        ticker = ticker.upper().strip()

        cached = self._load_cache(ticker)
        if cached:
            return cached

        # جرب API أولاً إذا عنده مفتاح
        if self.api_key:
            result = self._via_api(ticker)
            if result:
                self._save_cache(ticker, result)
                return result

        # بدون مفتاح → scrape الموقع
        result = self._via_scrape(ticker)
        if result:
            self._save_cache(ticker, result)
            return result

        # لم نجد بيانات
        return {
            "ticker": ticker,
            "halal": False,
            "purification_rate": None,
            "status": "UNKNOWN",
            "sector": "",
            "reason": "لم يُعثر على بيانات — مرفوض احتياطاً",
        }

    def screen_list(self, tickers: list[str]) -> dict:
        halal, rejected = [], {}
        for ticker in tickers:
            r = self.is_halal_zero(ticker)
            if r["halal"]:
                halal.append(ticker)
            else:
                rejected[ticker] = r["reason"]
            time.sleep(0.4)          # لا تُغرق الموقع
        return {
            "halal": halal,
            "rejected": rejected,
            "total": len(tickers),
            "halal_count": len(halal),
        }

    # ── طريقة 1: API رسمي (إذا توفّر المفتاح) ───────────────────────────────

    def _via_api(self, ticker: str) -> Optional[dict]:
        try:
            resp = self._session.get(
                f"https://api.musaffa.com/v1/instruments/{ticker}",
                headers={"apiKey": self.api_key},
                timeout=10,
            )
            if resp.status_code in (401, 403, 404):
                return None
            resp.raise_for_status()
            data = resp.json()
            return self._parse_api_response(ticker, data)
        except Exception as e:
            logger.warning(f"API failed for {ticker}: {e}")
            return None

    def _parse_api_response(self, ticker: str, data: dict) -> dict:
        status      = data.get("shariaComplianceStatus", "")
        purification = float(data.get("purificationPercentage") or 0)
        halal        = status == "COMPLIANT" and purification == 0.0
        return {
            "ticker": ticker,
            "halal": halal,
            "purification_rate": purification,
            "status": status,
            "sector": data.get("businessSector", ""),
            "reason": "" if halal else (
                f"الحالة: {status}" if status != "COMPLIANT"
                else f"تطهير {purification}% > 0%"
            ),
        }

    # ── طريقة 2: Scraping موقع Musaffa ───────────────────────────────────────

    def _via_scrape(self, ticker: str) -> Optional[dict]:
        """
        يفتح صفحة musaffa.com/stock/TICKER ويستخرج:
          - الحالة الشرعية
          - نسبة التطهير
        """
        url = f"https://musaffa.com/stock/{ticker}"
        try:
            resp = self._session.get(url, timeout=15)
            if resp.status_code == 404:
                logger.info(f"Musaffa: {ticker} غير موجود في الموقع")
                return None
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Scrape fetch failed {ticker}: {e}")
            return None

        # ── محاولة 1: JSON داخل __NEXT_DATA__ (Next.js) ─────────────────────
        result = self._parse_nextjs_data(ticker, resp.text)
        if result:
            return result

        # ── محاولة 2: JSON-LD أو window.__data__ ────────────────────────────
        result = self._parse_inline_json(ticker, resp.text)
        if result:
            return result

        # ── محاولة 3: قراءة HTML مباشرة ─────────────────────────────────────
        return self._parse_html(ticker, resp.text)

    def _parse_nextjs_data(self, ticker: str, html: str) -> Optional[dict]:
        """موقع Musaffa مبني بـ Next.js — البيانات موجودة في __NEXT_DATA__"""
        try:
            match = re.search(
                r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                html, re.DOTALL
            )
            if not match:
                return None

            data = json.loads(match.group(1))

            # تصفح الـ JSON للبحث عن compliance data
            props = data.get("props", {}).get("pageProps", {})

            # جرّب مسارات شائعة
            for key in ("stockData", "instrument", "stock", "data"):
                item = props.get(key, {})
                if isinstance(item, dict):
                    result = self._extract_from_dict(ticker, item)
                    if result:
                        return result

            # بحث عميق
            return self._deep_search(ticker, props)

        except Exception as e:
            logger.debug(f"NextJS parse failed {ticker}: {e}")
            return None

    def _parse_inline_json(self, ticker: str, html: str) -> Optional[dict]:
        """يبحث عن JSON مضمّن في الصفحة (window.* أو JSON-LD)"""
        try:
            # JSON-LD
            for match in re.finditer(
                r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
                html, re.DOTALL
            ):
                try:
                    obj = json.loads(match.group(1))
                    r = self._extract_from_dict(ticker, obj)
                    if r:
                        return r
                except Exception:
                    continue

            # window.* assignments
            for match in re.finditer(
                r'window\.__\w+\s*=\s*(\{.*?\});', html, re.DOTALL
            ):
                try:
                    obj = json.loads(match.group(1))
                    r = self._deep_search(ticker, obj)
                    if r:
                        return r
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Inline JSON parse failed {ticker}: {e}")
        return None

    def _parse_html(self, ticker: str, html: str) -> Optional[dict]:
        """قراءة HTML مباشرة بـ BeautifulSoup"""
        try:
            soup = BeautifulSoup(html, "lxml")

            # ── نسبة التطهير ─────────────────────────────────────────────────
            purification = 0.0
            for el in soup.find_all(string=re.compile(r'purif|تطهير', re.I)):
                nums = re.findall(r'[\d.]+', str(el.parent))
                if nums:
                    purification = float(nums[0])
                    break

            # ── الحالة الشرعية ───────────────────────────────────────────────
            status = "UNKNOWN"
            text   = soup.get_text(" ").upper()

            if "NON_COMPLIANT" in text or "NON-COMPLIANT" in text:
                status = "NON_COMPLIANT"
            elif "COMPLIANT" in text:
                status = "COMPLIANT"
            elif "QUESTIONABLE" in text or "DOUBTFUL" in text:
                status = "QUESTIONABLE"
            elif "HALAL" in text:
                status = "COMPLIANT"
            elif "HARAM" in text or "NOT PERMISSIBLE" in text:
                status = "NON_COMPLIANT"

            if status == "UNKNOWN":
                return None

            halal = status == "COMPLIANT" and purification == 0.0
            return {
                "ticker": ticker,
                "halal": halal,
                "purification_rate": purification,
                "status": status,
                "sector": "",
                "reason": "" if halal else (
                    f"الحالة: {status}" if status != "COMPLIANT"
                    else f"تطهير {purification}% > 0%"
                ),
            }
        except Exception as e:
            logger.warning(f"HTML parse failed {ticker}: {e}")
            return None

    # ── أدوات مساعدة ─────────────────────────────────────────────────────────

    def _extract_from_dict(self, ticker: str, d: dict) -> Optional[dict]:
        """يستخرج compliance من dict إذا وجد المفاتيح المطلوبة"""
        status_keys = [
            "shariaComplianceStatus", "complianceStatus",
            "sharia_status", "islamicStatus", "status",
        ]
        purif_keys  = [
            "purificationPercentage", "purificationRatio",
            "purification", "purif_pct",
        ]

        status = None
        for k in status_keys:
            if k in d and d[k]:
                status = str(d[k]).upper()
                break

        if not status:
            return None

        purification = 0.0
        for k in purif_keys:
            if k in d and d[k] is not None:
                purification = float(d[k])
                # تحويل نسبة عشرية إلى مئوية
                if 0 < purification < 1:
                    purification *= 100
                break

        # توحيد الحالة
        if "NON" in status or "HARAM" in status or "NOT" in status:
            status = "NON_COMPLIANT"
        elif "COMPLIANT" in status or "HALAL" in status or "PERMISSIBLE" in status:
            status = "COMPLIANT"
        elif "QUESTION" in status or "DOUBT" in status:
            status = "QUESTIONABLE"

        halal = status == "COMPLIANT" and purification == 0.0
        return {
            "ticker": ticker,
            "halal": halal,
            "purification_rate": round(purification, 4),
            "status": status,
            "sector": d.get("businessSector") or d.get("sector") or "",
            "reason": "" if halal else (
                f"الحالة: {status}" if status != "COMPLIANT"
                else f"تطهير {purification}% > 0%"
            ),
        }

    def _deep_search(self, ticker: str, obj, depth: int = 0) -> Optional[dict]:
        """بحث عميق في JSON متداخل"""
        if depth > 5:
            return None
        if isinstance(obj, dict):
            r = self._extract_from_dict(ticker, obj)
            if r:
                return r
            for v in obj.values():
                r = self._deep_search(ticker, v, depth + 1)
                if r:
                    return r
        elif isinstance(obj, list):
            for item in obj[:10]:
                r = self._deep_search(ticker, item, depth + 1)
                if r:
                    return r
        return None

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _load_cache(self, ticker: str) -> Optional[dict]:
        path = CACHE_DIR / f"{ticker}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if datetime.now() - datetime.fromisoformat(data["_at"]) > CACHE_TTL:
                return None
            return data
        except Exception:
            return None

    def _save_cache(self, ticker: str, result: dict):
        path = CACHE_DIR / f"{ticker}.json"
        try:
            path.write_text(json.dumps(
                {**result, "_at": datetime.now().isoformat()},
                ensure_ascii=False, indent=2
            ))
        except Exception:
            pass
