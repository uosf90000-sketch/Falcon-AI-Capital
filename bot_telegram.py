"""
Telegram Bot — فلتر الأسهم الحلال عبر Musaffa
يشغّله Railway مع البوت الرئيسي
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from musaffa_client import MusaffaClient

logging.basicConfig(level=logging.INFO)
musaffa = MusaffaClient()


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 *Falcon AI Capital — فلتر الأسهم الحلال*\n\n"
        "أرسل رمز السهم لأتحقق منه:\n"
        "مثال: `PANW` أو `/check PANW CRWD FTNT`",
        parse_mode="Markdown"
    )


async def check_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """أمر: /check PANW CRWD AAPL"""
    tickers = [t.upper() for t in ctx.args if t.strip()]
    if not tickers:
        await update.message.reply_text("أرسل رموز الأسهم بعد الأمر\nمثال: `/check PANW CRWD`", parse_mode="Markdown")
        return

    await update.message.reply_text("⏳ جاري الفحص...")
    result = musaffa.screen_list(tickers)
    await update.message.reply_text(_format_result(result), parse_mode="Markdown")


async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """إذا المستخدم أرسل رمز سهم مباشرة (مثل: PANW)"""
    text = update.message.text.upper().strip()
    words = text.split()

    # إذا كلمة واحدة أو كلمات قصيرة = رموز أسهم
    if all(len(w) <= 6 and w.isalpha() for w in words):
        await update.message.reply_text("⏳ جاري الفحص...")
        result = musaffa.screen_list(words)
        await update.message.reply_text(_format_result(result), parse_mode="Markdown")


def _format_result(result: dict) -> str:
    lines = [f"📊 *نتيجة الفحص الشرعي*\n"]

    if result["halal"]:
        lines.append("✅ *حلال 100% (تطهير صفر):*")
        for t in result["halal"]:
            lines.append(f"  • `{t}`")
    else:
        lines.append("⚠️ لا يوجد أسهم حلال في القائمة")

    if result["rejected"]:
        lines.append("\n❌ *مرفوضة:*")
        for t, reason in result["rejected"].items():
            lines.append(f"  • `{t}` — {reason}")

    lines.append(f"\n📈 الإجمالي: {result['total']} | حلال: {result['halal_count']}")
    return "\n".join(lines)


if __name__ == "__main__":
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    app.run_polling()
