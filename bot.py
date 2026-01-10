import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # пока просто читаем, можно не задавать

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "AInexus запущен ✅\n\nНапиши сообщение — отвечу.\n"
        "Если OpenAI-ключ не задан — отвечаю в режиме эхо."
    )

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""

    # Пока без OpenAI — чтобы стабильно работало.
    if not OPENAI_API_KEY:
        await update.message.reply_text(f"Ты написал: {text}")
        return

    # Заглушка: ключ есть, но “умный” ответ подключим следующим шагом
    await update.message.reply_text("✅ OpenAI-ключ вижу, следующий шаг — подключаем ответы от OpenAI.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # ВАЖНО: только polling, никаких webhooks
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()



