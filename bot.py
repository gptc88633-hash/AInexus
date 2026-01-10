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

# ---------------- CONFIG ----------------

logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY не задан")

client = OpenAI(api_key=OPENAI_API_KEY)

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 AInexus запущен\n\n"
        "Напиши любой вопрос — я отвечу с помощью OpenAI."
    )

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты полезный, вежливый AI-ассистент."},
                {"role": "user", "content": user_text},
            ],
            temperature=0.7,
        )

        answer = response.choices[0].message.content
        await update.message.reply_text(answer)

    except Exception as e:
        logging.exception("Ошибка OpenAI")
        await update.message.reply_text(
            "⚠️ OpenAI временно недоступен. Попробуй ещё раз через минуту."
        )

# ---------------- MAIN ----------------

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_reply))

    app.run_polling()

if __name__ == "__main__":
    main()




