"""
Falcon Sharia Bot — تيليغرام
أرسل رمز السهم واحصل على الحكم الشرعي فوراً.

تشغيل:
  TELEGRAM_TOKEN=توكنك python telegram_bot.py
"""

import os
import sys
import logging
import urllib.request
import urllib.parse
import json
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from filters import sharia_list

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_TOKEN"]
BASE  = f"https://api.telegram.org/bot{TOKEN}"


def send(chat_id: int, text: str):
    url  = f"{BASE}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "HTML",
    }).encode()
    urllib.request.urlopen(url, data=data, timeout=10)


def handle(message: dict):
    chat_id = message["chat"]["id"]
    text    = message.get("text", "").strip().upper()

    if not text or text.startswith("/"):
        send(chat_id, (
            "أهلاً! 👋\n"
            "أرسل رمز أي سهم وأخبرك هل هو حلال 100%:\n\n"
            "مثال: <b>PANW</b> أو <b>CRWD</b> أو <b>AAPL</b>"
        ))
        return

    result = sharia_list.check(text)

    if result["decision"] == "BUY_ALLOWED":
        reply = (
            f"✅ <b>{text}</b> — حلال\n"
            f"نسبة التطهير: <b>0%</b>\n"
            f"القرار: <b>BUY_ALLOWED</b>"
        )
    else:
        purif = result["purification"]
        purif_str = f"{purif}%" if purif is not None else "غير محدد"
        reply = (
            f"❌ <b>{text}</b> — {result['reason']}\n"
            f"نسبة التطهير: <b>{purif_str}</b>\n"
            f"القرار: <b>SHARIA_REJECTED</b>"
        )

    send(chat_id, reply)
    logger.info(f"{text} → {result['decision']}")


def run():
    logger.info("Falcon Sharia Bot يعمل ...")
    offset = 0
    while True:
        try:
            url  = f"{BASE}/getUpdates?offset={offset}&timeout=30"
            resp = urllib.request.urlopen(url, timeout=35)
            data = json.loads(resp.read())

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update:
                    handle(update["message"])

        except Exception as e:
            logger.error(f"خطأ: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run()
