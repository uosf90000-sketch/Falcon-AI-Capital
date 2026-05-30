"""
Musaffa Client — 4 طرق بالترتيب:
  1. كوكيز محفوظة من المتصفح (MUSAFFA_COOKIES) ← الأفضل عند وجود OTP
  2. تسجيل دخول Musaffa (email + password) بدون OTP
  3. Zoya Finance API (بديل مجاني)
  4. قوائم محلية مُدقّقة (احتياطي دائم)
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

logger = logging.getLogger(__name__)

CACHE_DIR = Path("cache/musaffa")
CACHE_TTL  = timedelta(hours=24)

# ── قوائم محلية احتياطية ─────────────────────────────────────────────────────
_HARAM = {
    "JPM","BAC","WFC","C","GS","MS","AXP","COF","DFS",          # بنوك
    "MET","PRU","AIG","AFL","ALL","CB","TRV","PGR",              # تأمين
    "PM","MO","BTI","STZ","BUD","TAP",                           # كحول/تبغ
    "MGM","WYNN","LVS","CZR","DKNG",                             # قمار
    "LMT","RTX","NOC","GD","BA",                                 # أسلحة
}
_HAS_PURIF = {
    "AAPL","NVDA","MSFT","GOOGL","GOOG","AMZN","META","TSLA",
    "AMGN","GILD",
}
_HALAL_ZERO = {
    "PANW","CRWD","FTNT","ZS","OKTA",
    "ANSS","SNPS","CDNS","PTC",
    "EPAM","GLOB",
    "IDXX","HOLX","PODD","INSP",
    "ROK","NOVT","ESAB",
    "NEE","BEP","CWEN",
}


class MusaffaClient:

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    COOKIES_FILE = Path("cache/musaffa_session.json")

    def __init__(
        self,
        api_key:  str = "",
        email:    str = "",
        password: str = "",
        zoya_key: str = "",
    ):
        self.api_key   = api_key   or os.getenv("MUSAFFA_API_KEY",  "")
        self.email     = email     or os.getenv("MUSAFFA_EMAIL",    "")
        self.password  = password  or os.getenv("MUSAFFA_PASSWORD", "")
        self.zoya_key  = zoya_key  or os.getenv("ZOYA_API_KEY",     "")

        # كوكيز يدوية من المتصفح (عند وجود OTP)
        self._cookies_env = os.getenv("MUSAFFA_COOKIES", "")

        self._session   = requests.Session()
        self._session.headers.update(self.HEADERS)
        self._logged_in = False

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)

    # ── نقطة الدخول ──────────────────────────────────────────────────────────

    def is_halal_zero(self, ticker: str) -> dict:
        ticker = ticker.upper().strip()

        cached = self._load_cache(ticker)
        if cached:
            return cached

        # 1. Musaffa API رسمي
        if self.api_key:
            r = self._musaffa_api(ticker)
            if r:
                return self._cache_and_return(ticker, r)

        # 2. كوكيز من المتصفح (حل OTP)
        if not self._logged_in:
            self._load_session()

        if self._logged_in:
            r = self._musaffa_scrape(ticker)
            if r:
                return self._cache_and_return(ticker, r)

        # 3. login تقليدي (بدون OTP)
        if self.email and self.password and not self._logged_in:
            self._musaffa_login()
            if self._logged_in:
                r = self._musaffa_scrape(ticker)
                if r:
                    return self._cache_and_return(ticker, r)

        # 4. Zoya Finance
        if self.zoya_key:
            r = self._zoya(ticker)
            if r:
                return self._cache_and_return(ticker, r)

        # 5. قوائم محلية
        return self._cache_and_return(ticker, self._local_lists(ticker))

    def screen_list(self, tickers: list[str]) -> dict:
        halal, rejected = [], {}
        for t in tickers:
            r = self.is_halal_zero(t)
            if r["halal"]:
                halal.append(t)
            else:
                rejected[t] = r["reason"]
            time.sleep(0.5)
        return {"halal": halal, "rejected": rejected,
                "total": len(tickers), "halal_count": len(halal)}

    # ── 1. Musaffa API رسمي ───────────────────────────────────────────────────

    def _musaffa_api(self, ticker: str) -> Optional[dict]:
        try:
            r = self._session.get(
                f"https://api.musaffa.com/v1/instruments/{ticker}",
                headers={"apiKey": self.api_key}, timeout=10,
            )
            if r.status_code in (401, 403, 404):
                return None
            r.raise_for_status()
            return self._parse(ticker, r.json())
        except Exception as e:
            logger.warning(f"Musaffa API error {ticker}: {e}")
            return None

    # ── 2. كوكيز المتصفح (حل OTP) ────────────────────────────────────────────

    def _load_session(self):
        """
        يحمّل الكوكيز من مصدرين:
          أ) MUSAFFA_COOKIES في env (Railway) — JSON string
          ب) ملف cache/musaffa_session.json — محفوظ من setup_musaffa.py
        """
        # أ) من env مباشرة
        if self._cookies_env:
            try:
                cookies = json.loads(self._cookies_env)
                if isinstance(cookies, list):
                    # صيغة Cookie-Editor (قائمة objects)
                    for c in cookies:
                        self._session.cookies.set(c["name"], c["value"])
                elif isinstance(cookies, dict):
                    # صيغة بسيطة {name: value}
                    for name, value in cookies.items():
                        self._session.cookies.set(name, value)
                self._logged_in = True
                logger.info("Musaffa: كوكيز من env محمّلة ✅")
                return
            except Exception as e:
                logger.warning(f"MUSAFFA_COOKIES parse error: {e}")

        # ب) من ملف محفوظ
        if not self.COOKIES_FILE.exists():
            return
        try:
            data     = json.loads(self.COOKIES_FILE.read_text())
            saved_at = datetime.fromisoformat(data.get("_saved_at", "2000-01-01"))
            if datetime.now() - saved_at > timedelta(days=30):
                logger.info("Musaffa: الكوكيز انتهت صلاحيتها — سجّل دخول من جديد")
                return
            for name, value in data.get("cookies", {}).items():
                self._session.cookies.set(name, value)
            self._logged_in = True
            logger.info("Musaffa: كوكيز من الملف محمّلة ✅")
        except Exception as e:
            logger.warning(f"Session file load error: {e}")

    def save_session(self):
        """احفظ الكوكيز الحالية — استخدمه بعد تسجيل الدخول اليدوي"""
        cookies = {k: v for k, v in self._session.cookies.items()}
        self.COOKIES_FILE.write_text(json.dumps({
            "_saved_at": datetime.now().isoformat(),
            "cookies": cookies,
        }, ensure_ascii=False, indent=2))
        logger.info(f"Session saved → {self.COOKIES_FILE}")

    # ── 3. Musaffa Login تقليدي ───────────────────────────────────────────────

    def _musaffa_login(self):
        """
        يسجّل دخول Musaffa بـ email/password.
        يحتاج: MUSAFFA_EMAIL و MUSAFFA_PASSWORD في .env
        """
        try:
            # أ) جيب CSRF token (NextAuth)
            csrf = self._session.get(
                "https://musaffa.com/api/auth/csrf", timeout=10
            ).json().get("csrfToken", "")

            # ب) سجّل دخول
            resp = self._session.post(
                "https://musaffa.com/api/auth/callback/credentials",
                data={
                    "email":       self.email,
                    "password":    self.password,
                    "csrfToken":   csrf,
                    "callbackUrl": "https://musaffa.com/",
                    "json":        "true",
                },
                timeout=15,
                allow_redirects=True,
            )

            # تحقق من نجاح الدخول
            if resp.ok and "session" in self._session.cookies.get_dict():
                self._logged_in = True
                logger.info("Musaffa: تسجيل الدخول نجح ✅")
            else:
                # جرّب endpoint بديل
                resp2 = self._session.post(
                    "https://musaffa.com/api/user/login",
                    json={"email": self.email, "password": self.password},
                    timeout=15,
                )
                self._logged_in = resp2.ok
                if self._logged_in:
                    logger.info("Musaffa: دخول عبر /api/user/login ✅")
                else:
                    logger.warning("Musaffa: فشل تسجيل الدخول")

        except Exception as e:
            logger.error(f"Musaffa login exception: {e}")
            self._logged_in = False

    def _musaffa_scrape(self, ticker: str) -> Optional[dict]:
        """يسحب بيانات السهم بعد تسجيل الدخول"""
        # جرّب API داخلي أولاً
        for endpoint in [
            f"https://musaffa.com/api/stocks/{ticker}/compliance",
            f"https://musaffa.com/api/v1/instruments/{ticker}",
            f"https://musaffa.com/api/screener/stocks/{ticker}",
        ]:
            try:
                r = self._session.get(endpoint, timeout=10)
                if r.ok and r.headers.get("content-type", "").startswith("application/json"):
                    result = self._parse(ticker, r.json())
                    if result:
                        return result
            except Exception:
                continue

        # ثم اقرأ صفحة السهم HTML
        try:
            r = self._session.get(
                f"https://musaffa.com/stock/{ticker}", timeout=15
            )
            if not r.ok:
                return None
            return self._parse_nextjs(ticker, r.text)
        except Exception as e:
            logger.warning(f"Musaffa scrape error {ticker}: {e}")
            return None

    # ── 3. Zoya Finance ───────────────────────────────────────────────────────

    def _zoya(self, ticker: str) -> Optional[dict]:
        query = """
        query($t: String!) {
          stockReport(ticker: $t) {
            ticker complianceStatus purificationRatio businessSector
          }
        }"""
        try:
            r = self._session.post(
                "https://api.zoya.finance/graphql",
                json={"query": query, "variables": {"t": ticker}},
                headers={"Authorization": f"Bearer {self.zoya_key}"},
                timeout=10,
            )
            r.raise_for_status()
            d = r.json().get("data", {}).get("stockReport") or {}
            if not d:
                return None
            status = d.get("complianceStatus", "")
            purif  = round(float(d.get("purificationRatio") or 0) * 100, 4)
            halal  = status == "COMPLIANT" and purif == 0.0
            return {
                "ticker": ticker, "halal": halal,
                "purification_rate": purif, "status": status,
                "sector": d.get("businessSector", ""),
                "reason": "" if halal else (
                    f"Zoya: {status}" if status != "COMPLIANT"
                    else f"تطهير {purif}%"
                ),
            }
        except Exception as e:
            logger.warning(f"Zoya error {ticker}: {e}")
            return None

    # ── 4. قوائم محلية ───────────────────────────────────────────────────────

    def _local_lists(self, ticker: str) -> dict:
        if ticker in _HARAM:
            return self._make(ticker, False, 0, "NON_COMPLIANT", "سهم محظور")
        if ticker in _HAS_PURIF:
            return self._make(ticker, False, 0, "COMPLIANT", "حلال لكن فيه تطهير > 0%")
        if ticker in _HALAL_ZERO:
            return self._make(ticker, True,  0, "COMPLIANT", "")
        # مجهول → رفض احتياطاً
        return self._make(ticker, False, None, "UNKNOWN",
                          "غير موجود في قواعد البيانات — مرفوض احتياطاً")

    # ── مساعدات ──────────────────────────────────────────────────────────────

    def _parse(self, ticker: str, d: dict) -> Optional[dict]:
        for sk in ("shariaComplianceStatus","complianceStatus","islamicStatus","status"):
            status = d.get(sk)
            if status:
                break
        else:
            return None

        status = str(status).upper()
        if "NON" in status or "HARAM" in status:
            status = "NON_COMPLIANT"
        elif "COMPLIANT" in status or "HALAL" in status:
            status = "COMPLIANT"
        elif "QUESTION" in status or "DOUBT" in status:
            status = "QUESTIONABLE"

        purif = 0.0
        for pk in ("purificationPercentage","purificationRatio","purification"):
            v = d.get(pk)
            if v is not None:
                purif = float(v)
                if 0 < purif < 1:
                    purif *= 100
                break

        halal = status == "COMPLIANT" and purif == 0.0
        return {
            "ticker": ticker, "halal": halal,
            "purification_rate": round(purif, 4), "status": status,
            "sector": d.get("businessSector") or d.get("sector") or "",
            "reason": "" if halal else (
                f"الحالة: {status}" if status != "COMPLIANT"
                else f"تطهير {purif}%"
            ),
        }

    def _parse_nextjs(self, ticker: str, html: str) -> Optional[dict]:
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if not m:
            return None
        try:
            data  = json.loads(m.group(1))
            props = data.get("props", {}).get("pageProps", {})
            return self._deep_search(ticker, props)
        except Exception:
            return None

    def _deep_search(self, ticker: str, obj, depth: int = 0) -> Optional[dict]:
        if depth > 6:
            return None
        if isinstance(obj, dict):
            r = self._parse(ticker, obj)
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

    @staticmethod
    def _make(ticker, halal, purif, status, reason) -> dict:
        return {"ticker": ticker, "halal": halal,
                "purification_rate": purif, "status": status,
                "sector": "", "reason": reason}

    def _cache_and_return(self, ticker: str, result: dict) -> dict:
        self._save_cache(ticker, result)
        return result

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _load_cache(self, ticker: str) -> Optional[dict]:
        path = CACHE_DIR / f"{ticker}.json"
        if not path.exists():
            return None
        try:
            d = json.loads(path.read_text())
            if datetime.now() - datetime.fromisoformat(d["_at"]) > CACHE_TTL:
                return None
            return d
        except Exception:
            return None

    def _save_cache(self, ticker: str, result: dict):
        try:
            path = CACHE_DIR / f"{ticker}.json"
            path.write_text(json.dumps(
                {**result, "_at": datetime.now().isoformat()},
                ensure_ascii=False, indent=2
            ))
        except Exception:
            pass
