import os
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Alnexus запущен ✅\n\nНапиши сообщение — отвечу."
    )

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    await update.message.reply_text(f"Ты написал: {text}")

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")
    if not RENDER_EXTERNAL_URL:
        raise RuntimeError("Не задана переменная окружения RENDER_EXTERNAL_URL (публичный URL Render)")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # ВАЖНО: webhook, без polling
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", "10000")),
        webhook_url=f"{RENDER_EXTERNAL_URL}/{TELEGRAM_BOT_TOKEN}",
        url_path=TELEGRAM_BOT_TOKEN,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()



