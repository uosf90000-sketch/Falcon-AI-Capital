"""
setup_musaffa.py — شغّله مرة وحدة لنسخ كوكيز Musaffa
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
الخطوات:
  1. افتح musaffa.com في المتصفح وسجّل دخول (مع OTP)
  2. انسخ الكوكيز (راجع التعليمات في الأسفل)
  3. شغّل هذا السكريبت وألصق الكوكيز
  4. الكوكيز تُحفظ في cache/musaffa_session.json
  5. البوت يستخدمها تلقائياً لمدة 30 يوم
"""

import json
import sys
from pathlib import Path
from musaffa_client import MusaffaClient

COOKIES_FILE = Path("cache/musaffa_session.json")

INSTRUCTIONS = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
كيف تنسخ الكوكيز من المتصفح؟
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chrome / Edge:
  1. سجّل دخول على musaffa.com (مع OTP)
  2. ثبّت إضافة "Cookie-Editor"
     chrome.google.com/webstore/detail/cookie-editor
  3. افتح الإضافة وهو على الموقع
  4. اضغط "Export" → "Export as JSON"
  5. انسخ كل النص

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
بديل — نسخ يدوي من DevTools:
  1. F12 → Application → Cookies → musaffa.com
  2. انسخ قيمة الكوكيز المهمة
     (عادةً: next-auth.session-token أو similar)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def main():
    print(INSTRUCTIONS)
    print("الصق الكوكيز (JSON) ثم اضغط Enter مرتين:\n")

    lines = []
    while True:
        try:
            line = input()
            if line == "" and lines:
                break
            lines.append(line)
        except EOFError:
            break

    raw = "\n".join(lines).strip()
    if not raw:
        print("❌ لم تُلصق أي شيء")
        sys.exit(1)

    # تحقق صيغة JSON
    try:
        cookies_data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ صيغة JSON غلط: {e}")
        sys.exit(1)

    # حوّل لـ dict بسيط
    if isinstance(cookies_data, list):
        # صيغة Cookie-Editor
        cookies = {c["name"]: c["value"] for c in cookies_data if "name" in c}
    elif isinstance(cookies_data, dict):
        cookies = cookies_data
    else:
        print("❌ صيغة غير معروفة")
        sys.exit(1)

    if not cookies:
        print("❌ لا توجد كوكيز")
        sys.exit(1)

    # احفظ
    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    COOKIES_FILE.write_text(json.dumps({
        "_saved_at": datetime.now().isoformat(),
        "cookies": cookies,
    }, ensure_ascii=False, indent=2))

    print(f"\n✅ تم حفظ {len(cookies)} كوكي في {COOKIES_FILE}")

    # اختبر أنها تشتغل
    print("\n🔍 جاري اختبار الاتصال بـ Musaffa...")
    client = MusaffaClient()
    result = client.is_halal_zero("PANW")
    source = result.get("status", "")
    if result["halal"]:
        print(f"✅ الاتصال نجح — PANW: حلال ({source})")
    else:
        print(f"⚠️ PANW: {result['reason']}")
        print("   (إذا رجع من القوائم المحلية فالكوكيز ما اشتغلت)")

    # عرض للنسخ إلى Railway
    print("\n" + "━"*50)
    print("لإضافة الكوكيز إلى Railway كـ env var:")
    print("  Variable name:  MUSAFFA_COOKIES")
    print("  Variable value: " + json.dumps(cookies, ensure_ascii=False))
    print("━"*50)


if __name__ == "__main__":
    main()
