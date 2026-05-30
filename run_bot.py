"""
نقطة تشغيل البوت
─────────────────
ضع مفاتيحك هنا أو استخدم متغيرات البيئة:

  ALPACA_KEY=xxx ALPACA_SECRET=yyy python run_bot.py

Paper trading افتراضي — غيّر ALPACA_PAPER=false للتداول الحقيقي.
"""

import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("falcon_bot.log", encoding="utf-8"),
    ],
)

# ── اختياري: ضع مفاتيحك مباشرة (لا تحفظهم في git) ──────────────────────────
# os.environ["ALPACA_KEY"]    = "PKXXXXXXXXXXXXXXX"
# os.environ["ALPACA_SECRET"] = "XXXXXXXXXXXXXXXXX"
# os.environ["ZOYA_KEY"]      = "zoya_key_here"
# os.environ["ALPACA_PAPER"]  = "true"   ← paper trading

from bot.sharia_bot import ShariaBot

if __name__ == "__main__":
    ShariaBot().run()
