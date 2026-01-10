import os
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from openai import OpenAI

# -------------------- ЛОГИ --------------------
logging.basicConfig(level=logging.INFO)

# -------------------- ENV --------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# -------------------- OPENAI --------------------
client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------- HANDLERS --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if OPENAI_API_KEY:
        await update.message.reply_text(
            "AInexus запущен ✅\n\n"
            "OpenAI-ключ найден. Напиши сообщение — отвечу."
        )
    else:
        await update.message.reply_text(
            "AInexus запущен ✅\n\n"
            "⚠️ OpenAI-ключ не задан. Работаю в режиме эхо."
        )

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""

    # Если OpenAI не подключён — просто эхо
    if not client:
        await update.message.reply_text(f"Ты написал: {text}")
        return

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Ты дружелюбный Telegram-ассистент по имени AInexus."
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
        )

        answer = response.choices[0].message.content
        await update.message.reply_text(answer)

    except Exception as e:
        logging.exception(e)
        await update.message.reply_text(
            "⚠️ OpenAI сейчас недоступен. Попробуй позже."
        )

# -------------------- MAIN --------------------
def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    app.run_polling()

if __name__ == "__main__":
    main()



