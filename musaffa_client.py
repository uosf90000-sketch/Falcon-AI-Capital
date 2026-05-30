"""
Musaffa Client — بيانات حقيقية من musaffa.com
يسجّل دخول تلقائياً بإيميلك وكلمة السر من Railway env vars
"""

import os, re, json, logging, time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import requests

logger = logging.getLogger(__name__)

CACHE_DIR    = Path("cache/musaffa")
SESSION_FILE = Path("cache/musaffa_session.json")
CACHE_TTL    = timedelta(hours=24)
SESSION_TTL  = timedelta(days=25)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/html, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://musaffa.com/",
    "Origin":          "https://musaffa.com",
}


class MusaffaClient:

    def __init__(self, email="", password="", api_key=""):
        self.email    = email    or os.getenv("MUSAFFA_EMAIL",    "")
        self.password = password or os.getenv("MUSAFFA_PASSWORD", "")
        self.api_key  = api_key  or os.getenv("MUSAFFA_API_KEY",  "")
        self._cookies_env = os.getenv("MUSAFFA_COOKIES", "")

        self._s = requests.Session()
        self._s.headers.update(HEADERS)
        self._logged_in = False

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    # ── نقطة الدخول ──────────────────────────────────────────────────────────

    def is_halal_zero(self, ticker: str) -> dict:
        ticker = ticker.upper().strip()

        cached = self._load_cache(ticker)
        if cached:
            return cached

        result = self._get_from_musaffa(ticker)
        if result:
            self._save_cache(ticker, result)
            return result

        # احتياطي: قوائم محلية
        return self._save_cache(ticker, self._fallback(ticker))

    def screen_list(self, tickers: list[str]) -> dict:
        halal, rejected = [], {}
        for t in tickers:
            r = self.is_halal_zero(t)
            (halal if r["halal"] else rejected.update({t: r["reason"]} or [])) and halal.append(t) if r["halal"] else None
            if not r["halal"]:
                rejected[t] = r["reason"]
            time.sleep(0.5)
        return {"halal": halal, "rejected": rejected,
                "total": len(tickers), "halal_count": len(halal)}

    # ── منطق الحصول على البيانات ─────────────────────────────────────────────

    def _get_from_musaffa(self, ticker: str) -> Optional[dict]:
        # 1. API رسمي (إذا عنده مفتاح)
        if self.api_key:
            r = self._official_api(ticker)
            if r:
                return r

        # 2. تأكد من الجلسة النشطة
        if not self._logged_in:
            self._start_session()

        if not self._logged_in:
            logger.warning("Musaffa: لم يتم تسجيل الدخول — تحقق من MUSAFFA_EMAIL و MUSAFFA_PASSWORD")
            return None

        # 3. جرب API الداخلي أولاً (أسرع وأدق)
        r = self._internal_api(ticker)
        if r:
            return r

        # 4. اقرأ صفحة السهم
        return self._scrape_page(ticker)

    # ── تسجيل الدخول ─────────────────────────────────────────────────────────

    def _start_session(self):
        """يحاول تسجيل الدخول بكل الطرق المتاحة"""

        # أ) كوكيز محفوظة من env
        if self._load_cookies_env():
            return

        # ب) كوكيز من ملف (محفوظة سابقاً)
        if self._load_cookies_file():
            return

        # ج) تسجيل دخول بإيميل + كلمة سر
        if self.email and self.password:
            self._login_with_credentials()

    def _load_cookies_env(self) -> bool:
        if not self._cookies_env:
            return False
        try:
            cookies = json.loads(self._cookies_env)
            if isinstance(cookies, list):
                for c in cookies:
                    self._s.cookies.set(c["name"], c["value"])
            else:
                for k, v in cookies.items():
                    self._s.cookies.set(k, v)
            self._logged_in = self._verify_session()
            if self._logged_in:
                logger.info("Musaffa: دخول بكوكيز env ✅")
            return self._logged_in
        except Exception as e:
            logger.warning(f"MUSAFFA_COOKIES error: {e}")
            return False

    def _load_cookies_file(self) -> bool:
        if not SESSION_FILE.exists():
            return False
        try:
            data = json.loads(SESSION_FILE.read_text())
            saved = datetime.fromisoformat(data.get("_saved_at", "2000-01-01"))
            if datetime.now() - saved > SESSION_TTL:
                logger.info("Musaffa: الجلسة المحفوظة انتهت")
                return False
            for k, v in data.get("cookies", {}).items():
                self._s.cookies.set(k, v)
            self._logged_in = self._verify_session()
            if self._logged_in:
                logger.info("Musaffa: دخول بجلسة محفوظة ✅")
            return self._logged_in
        except Exception:
            return False

    def _login_with_credentials(self):
        """تسجيل دخول بإيميل + كلمة سر"""
        try:
            logger.info(f"Musaffa: محاولة دخول بـ {self.email}...")

            # خطوة 1: جيب CSRF token
            csrf = ""
            try:
                r = self._s.get("https://musaffa.com/api/auth/csrf", timeout=10)
                csrf = r.json().get("csrfToken", "")
            except Exception:
                pass

            # خطوة 2: سجّل دخول (NextAuth)
            resp = self._s.post(
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

            self._logged_in = self._verify_session()

            if self._logged_in:
                logger.info("Musaffa: تسجيل الدخول نجح ✅")
                self._save_cookies_file()
            else:
                logger.warning(
                    "Musaffa: فشل تسجيل الدخول ❌\n"
                    "السبب المحتمل:\n"
                    "  • كلمة السر خاطئة\n"
                    "  • الحساب يستخدم Google login\n"
                    "  • طلب OTP — استخدم setup_musaffa.py"
                )

        except Exception as e:
            logger.error(f"Musaffa login error: {e}")

    def _verify_session(self) -> bool:
        """يتحقق أن الجلسة فعّالة"""
        try:
            r = self._s.get("https://musaffa.com/api/auth/session", timeout=8)
            data = r.json()
            return bool(data.get("user") or data.get("email"))
        except Exception:
            return False

    def _save_cookies_file(self):
        """يحفظ الكوكيز للاستخدام اللاحق"""
        try:
            SESSION_FILE.write_text(json.dumps({
                "_saved_at": datetime.now().isoformat(),
                "cookies": dict(self._s.cookies),
            }, ensure_ascii=False, indent=2))
        except Exception:
            pass

    # ── جلب البيانات ─────────────────────────────────────────────────────────

    def _official_api(self, ticker: str) -> Optional[dict]:
        try:
            r = self._s.get(
                f"https://api.musaffa.com/v1/instruments/{ticker}",
                headers={"apiKey": self.api_key}, timeout=10,
            )
            if r.ok:
                return self._parse(ticker, r.json())
        except Exception:
            pass
        return None

    def _internal_api(self, ticker: str) -> Optional[dict]:
        """يجرب API الداخلي الذي يستخدمه الموقع بعد الدخول"""
        endpoints = [
            f"https://musaffa.com/api/stocks/{ticker}/compliance",
            f"https://musaffa.com/api/v1/instruments/{ticker}",
            f"https://musaffa.com/api/screener/stocks/{ticker}",
            f"https://musaffa.com/api/stock/{ticker}",
        ]
        for url in endpoints:
            try:
                r = self._s.get(url, timeout=10)
                if r.ok and "json" in r.headers.get("content-type", ""):
                    result = self._parse(ticker, r.json())
                    if result:
                        logger.info(f"Musaffa internal API: {ticker} ✅")
                        return result
            except Exception:
                continue
        return None

    def _scrape_page(self, ticker: str) -> Optional[dict]:
        """يقرأ صفحة السهم ويستخرج البيانات من __NEXT_DATA__"""
        try:
            r = self._s.get(f"https://musaffa.com/stock/{ticker}", timeout=15)
            if not r.ok:
                return None
            m = re.search(
                r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                r.text, re.DOTALL
            )
            if not m:
                return None
            data = json.loads(m.group(1))
            props = data.get("props", {}).get("pageProps", {})
            return self._deep_search(ticker, props)
        except Exception as e:
            logger.warning(f"Musaffa scrape error {ticker}: {e}")
            return None

    # ── تحليل البيانات ────────────────────────────────────────────────────────

    def _parse(self, ticker: str, d: dict) -> Optional[dict]:
        status = None
        for k in ("shariaComplianceStatus","complianceStatus","islamicStatus","status"):
            if d.get(k):
                status = str(d[k]).upper()
                break
        if not status:
            return None

        if "NON" in status or "HARAM" in status:
            status = "NON_COMPLIANT"
        elif "COMPLIANT" in status or "HALAL" in status:
            status = "COMPLIANT"
        elif "QUESTION" in status or "DOUBT" in status:
            status = "QUESTIONABLE"

        purif = 0.0
        for k in ("purificationPercentage","purificationRatio","purification"):
            if d.get(k) is not None:
                purif = float(d[k])
                if 0 < purif < 1:
                    purif *= 100
                break

        halal = status == "COMPLIANT" and purif == 0.0
        return {
            "ticker": ticker, "halal": halal,
            "purification_rate": round(purif, 4), "status": status,
            "sector": d.get("businessSector") or d.get("sector") or "",
            "source": "musaffa",
            "reason": "" if halal else (
                f"الحالة: {status}" if status != "COMPLIANT"
                else f"تطهير {purif}%"
            ),
        }

    def _deep_search(self, ticker: str, obj, depth=0) -> Optional[dict]:
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

    # ── احتياطي: قوائم محلية ─────────────────────────────────────────────────

    def _fallback(self, ticker: str) -> dict:
        from halal_universe import is_halal as etf_halal
        HARAM = {
            "JPM","BAC","WFC","C","GS","MS","AXP","COF","DFS",
            "MET","PRU","AIG","AFL","ALL","CB","TRV","PGR",
            "PM","MO","BTI","STZ","BUD","TAP",
            "MGM","WYNN","LVS","CZR","DKNG",
            "LMT","RTX","NOC","GD","BA",
        }
        HAS_PURIF = {
            "AAPL","NVDA","MSFT","GOOGL","GOOG",
            "AMZN","META","TSLA","AMGN","GILD",
        }
        if ticker in HARAM:
            return self._r(ticker, False, "NON_COMPLIANT", "سهم محظور")
        if ticker in HAS_PURIF:
            return self._r(ticker, False, "COMPLIANT",     "حلال لكن فيه تطهير > 0%")
        try:
            if etf_halal(ticker):
                return self._r(ticker, True, "COMPLIANT", "")
        except Exception:
            pass
        return self._r(ticker, False, "UNKNOWN", "غير موجود في Musaffa — مرفوض احتياطاً")

    @staticmethod
    def _r(ticker, halal, status, reason) -> dict:
        return {"ticker": ticker, "halal": halal, "purification_rate": 0.0 if halal else None,
                "status": status, "sector": "", "source": "local", "reason": reason}

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _load_cache(self, ticker: str) -> Optional[dict]:
        p = CACHE_DIR / f"{ticker}.json"
        if not p.exists():
            return None
        try:
            d = json.loads(p.read_text())
            if datetime.now() - datetime.fromisoformat(d["_at"]) > CACHE_TTL:
                return None
            return d
        except Exception:
            return None

    def _save_cache(self, ticker: str, result: dict) -> dict:
        try:
            (CACHE_DIR / f"{ticker}.json").write_text(
                json.dumps({**result, "_at": datetime.now().isoformat()},
                           ensure_ascii=False, indent=2)
            )
        except Exception:
            pass
        return result
