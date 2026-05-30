"""
Falcon AI Capital — نقطة التشغيل
──────────────────────────────────
ضع مفاتيحك هنا ثم شغّل:
  python run_bot.py
"""

import os
import logging
import sys

# ── المفاتيح من متغيرات البيئة أو ملف .env ──────────────────────────────────
# لا تضع المفاتيح هنا مباشرة — استخدم .env
# مثال:
#   ALPACA_KEY=PKxxxxxxx ALPACA_SECRET=xxxxxxx python run_bot.py
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
