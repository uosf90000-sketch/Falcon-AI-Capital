"""
Halal Universe — قائمة الأسهم الحلال من ETFs إسلامية معتمدة
تحديث تلقائي أسبوعي — لا يحتاج تسجيل دخول أو API key

المصادر:
  SPUS — SP Funds S&P 500 Sharia (AAOIFI معتمد، تطهير صفر)
  HLAL — Wahed FTSE USA Shariah ETF
  SPSK — SP Funds S&P Kensho Sharia
"""

import csv
import json
import logging
import io
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

CACHE_FILE = Path("cache/halal_universe.json")
CACHE_TTL  = timedelta(days=7)

ETFS = {
    "SPUS": "https://spfunds.com/spus/",
    "HLAL": "https://www.wahedinvest.com/wahed-ftse-usa-shariah-etf/",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ── قائمة أساسية مضمونة (تعمل بدون إنترنت) ──────────────────────────────────
BASE_HALAL = {
    # أمن سيبراني
    "PANW","CRWD","FTNT","ZS","OKTA","CYBR","S","TENB","QLYS",
    # برامج هندسية وتصميم
    "ANSS","SNPS","CDNS","PTC","ADSK","AZPN","BRKS",
    # خدمات تقنية
    "EPAM","GLOB","FLUT","EXLS","CACI","LDOS",
    # رعاية صحية وتقنية طبية
    "IDXX","HOLX","PODD","INSP","IRTC","MMSI","ITGR","NVCR","NVST",
    "TMDX","NTRA","RXRX","SDGR","VEEV",
    # صناعية ومعدات
    "ROK","NOVT","ESAB","GTLS","FELE","ITRI","REXR","TREX",
    # طاقة متجددة
    "NEE","BEP","CWEN","RUN","ENPH","FSLR","SEDG","ARRY","SHLS",
    # برمجيات SaaS
    "PAYC","PCTY","HUBS","WDAY","DDOG","MDB","NET","SNOW",
    "TTD","PUBM","MGNI","ZI","ALTR","BRZE","CFLT","CWAN",
    # رقائق إلكترونية (بدون دخل فوائد ذكر)
    "MPWR","ONTO","FORM","RMBS","ALGM","AEIS","DIOD","SITM",
    # تجارة إلكترونية ولوجستيات
    "GLBE","MNDY","WIX","SHOP",
    # ترفيه خالص (بدون كحول/قمار/محتوى بالغ)
    "RBLX","U","TTWO","EA","ZNGA",
    # استهلاكية حلال
    "LULU","ELF","CAVA","BROS","WING","TXRH",
    # عقارات صناعية (لا فوائد)
    "IIPR","COLD","STAG",
}


class HalalUniverse:

    def __init__(self):
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._tickers: Optional[set] = None

    def get_halal_tickers(self) -> set[str]:
        """يرجع مجموعة الأسهم الحلال — يحدّث تلقائياً كل أسبوع"""
        if self._tickers is not None:
            return self._tickers

        cached = self._load_cache()
        if cached:
            self._tickers = cached
            return self._tickers

        self._tickers = self._fetch_all_etfs()
        self._save_cache(self._tickers)
        return self._tickers

    def is_halal(self, ticker: str) -> bool:
        return ticker.upper() in self.get_halal_tickers()

    def refresh(self) -> int:
        """تحديث إجباري — يرجع عدد الأسهم"""
        self._tickers = self._fetch_all_etfs()
        self._save_cache(self._tickers)
        logger.info(f"HalalUniverse refreshed: {len(self._tickers)} tickers")
        return len(self._tickers)

    # ── تحميل ETFs ────────────────────────────────────────────────────────────

    def _fetch_all_etfs(self) -> set[str]:
        tickers = set(BASE_HALAL)

        for etf_name, url in ETFS.items():
            fetched = self._fetch_etf(etf_name, url)
            if fetched:
                logger.info(f"{etf_name}: {len(fetched)} أسهم")
                tickers |= fetched
            else:
                logger.warning(f"{etf_name}: فشل التحميل — نستخدم القائمة الأساسية")

        return tickers

    def _fetch_etf(self, name: str, url: str) -> Optional[set[str]]:
        """يجلب أسهم ETF من Yahoo Finance (أكثر موثوقية)"""
        return self._fetch_from_yahoo(name)

    def _fetch_from_yahoo(self, etf_symbol: str) -> Optional[set[str]]:
        """
        يجلب top holdings من Yahoo Finance.
        مجاني بدون مفتاح — يرجع أكبر 25 سهم.
        """
        try:
            resp = requests.get(
                f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{etf_symbol}",
                params={"modules": "topHoldings"},
                headers={**HEADERS, "Accept": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
            result = resp.json()
            holdings = (
                result
                .get("quoteSummary", {})
                .get("result", [{}])[0]
                .get("topHoldings", {})
                .get("holdings", [])
            )
            tickers = set()
            for h in holdings:
                sym = h.get("symbol", "").upper().strip()
                if sym and sym.isalpha() and len(sym) <= 6:
                    tickers.add(sym)
            return tickers if tickers else None
        except Exception as e:
            logger.warning(f"Yahoo ETF fetch failed [{etf_symbol}]: {e}")
            return None

    def _parse_csv(self, text: str) -> set[str]:
        """يستخرج رموز الأسهم من CSV — يدعم صيغ مختلفة"""
        tickers = set()
        reader  = csv.reader(io.StringIO(text))

        ticker_cols = {"ticker","symbol","holding ticker","cusip","sedol"}
        col_idx     = None

        for i, row in enumerate(reader):
            if not row:
                continue

            # اكتشف عمود الـ ticker من السطر الأول (header)
            if col_idx is None:
                headers_lower = [c.lower().strip() for c in row]
                for idx, h in enumerate(headers_lower):
                    if h in ticker_cols:
                        col_idx = idx
                        break
                if col_idx is None and i == 0:
                    col_idx = 0   # افتراض: العمود الأول
                continue

            if col_idx < len(row):
                t = row[col_idx].strip().upper()
                # فقط رموز صحيحة (حروف إنجليزية 1-6)
                if t and t.isalpha() and 1 <= len(t) <= 6:
                    tickers.add(t)

        return tickers

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _load_cache(self) -> Optional[set[str]]:
        if not CACHE_FILE.exists():
            return None
        try:
            data = json.loads(CACHE_FILE.read_text())
            saved = datetime.fromisoformat(data["_saved_at"])
            if datetime.now() - saved > CACHE_TTL:
                logger.info("HalalUniverse cache expired — refreshing")
                return None
            tickers = set(data["tickers"])
            logger.info(f"HalalUniverse loaded from cache: {len(tickers)} tickers")
            return tickers
        except Exception:
            return None

    def _save_cache(self, tickers: set[str]):
        CACHE_FILE.write_text(json.dumps({
            "_saved_at": datetime.now().isoformat(),
            "_next_update": (datetime.now() + CACHE_TTL).strftime("%Y-%m-%d"),
            "count": len(tickers),
            "tickers": sorted(tickers),
        }, ensure_ascii=False, indent=2))


# singleton
_universe = HalalUniverse()


def is_halal(ticker: str) -> bool:
    return _universe.is_halal(ticker)


def get_all_halal() -> set[str]:
    return _universe.get_halal_tickers()


def refresh() -> int:
    return _universe.refresh()
