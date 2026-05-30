"""
Falcon AI Capital — نقطة التشغيل
──────────────────────────────────
ضع مفاتيحك هنا ثم شغّل:
  python run_bot.py
"""

import os
import logging
import sys

# ── ضع مفاتيحك هنا ───────────────────────────────────────────────────────────
os.environ["ALPACA_KEY"]    = "PKSM3LOLTJZUCJEOGZORVHAPTF"
os.environ["ALPACA_SECRET"] = "8Sjf2pdy1h675kvYY1ArwrSjNoAPNw7vbF1sx56VKmwU"
os.environ["ALPACA_PAPER"]  = "true"   # true = paper trading | false = حقيقي
os.environ["ZOYA_KEY"]      = ""       # اختياري — ضع مفتاح Zoya إذا عندك
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("falcon_bot.log", encoding="utf-8"),
    ],
)

from bot.falcon_bot import FalconBot

if __name__ == "__main__":
    FalconBot().run()
