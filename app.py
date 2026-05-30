"""
Falcon AI Capital — Halal Stock Screener API
يعمل على Railway — يستخدم Musaffa كمصدر رئيسي للفحص الشرعي
"""

import os
import logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from musaffa_client import MusaffaClient
from filters.islamic_filter import IslamicFilter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Falcon AI Capital — Halal Screener",
    description="يفلتر الأسهم ويعرض الحلال 100% (تطهير صفر) من Musaffa",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

musaffa = MusaffaClient(api_key=os.getenv("MUSAFFA_API_KEY", ""))
islamic_filter = IslamicFilter(
    zoya_api_key=os.getenv("ZOYA_API_KEY", ""),
    musaffa_api_key=os.getenv("MUSAFFA_API_KEY", ""),
)


class ScreenRequest(BaseModel):
    tickers: list[str]


@app.get("/")
def root():
    return {"status": "ok", "service": "Falcon AI Capital — Halal Screener"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/screen/{ticker}")
def screen_one(ticker: str):
    """
    يفحص سهم واحد — يرجع هل هو حلال 100% أم لا.
    مثال: GET /screen/PANW
    """
    result = musaffa.is_halal_zero(ticker.upper())
    return result


@app.post("/screen/batch")
def screen_batch(body: ScreenRequest):
    """
    يفحص قائمة أسهم دفعة واحدة.
    Body: {"tickers": ["PANW", "AAPL", "JPM", "CRWD"]}
    """
    if not body.tickers:
        raise HTTPException(status_code=400, detail="يجب إرسال قائمة أسهم")
    if len(body.tickers) > 100:
        raise HTTPException(status_code=400, detail="الحد الأقصى 100 سهم في طلب واحد")

    result = musaffa.screen_list(body.tickers)
    return result


@app.get("/screen")
def screen_query(
    tickers: str = Query(..., description="أسهم مفصولة بفواصل: PANW,CRWD,FTNT")
):
    """
    يفحص أسهم عبر query string.
    مثال: GET /screen?tickers=PANW,CRWD,FTNT
    """
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="أدخل رموز الأسهم")

    result = musaffa.screen_list(ticker_list)
    return result
