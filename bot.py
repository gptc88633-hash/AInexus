import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# OpenAI подключаем только если ключ задан
client = None
if OPENAI_API_KEY:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "Ты — AInexus, полезный ассистент. Отвечай по-русски, коротко и по делу."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "AInexus запущен ✅\n\nНапиши сообщение — отвечу."
    if not OPENAI_API_KEY:
        msg += "\n\n⚠️ OpenAI-ключ не задан — отвечаю в режиме эхо."
    await update.message.reply_text(msg)

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return

    # Если ключа нет — эхо
    if not client:
        await update.message.reply_text(f"Ты написал: {text}")
        return

    try:
        # Вариант 1: самый простой и стабильный — Chat Completions
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.6,
        )
        answer = resp.choices[0].message.content.strip()
        await update.message.reply_text(answer if answer else "Пустой ответ 🤔")
    except Exception as e:
        logging.exception("OpenAI error")
        await update.message.reply_text(
            "⚠️ OpenAI сейчас недоступен. Я живой, просто ИИ не ответил. "
            "Попробуй ещё раз через минуту."
        )

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.run_polling()

if __name__ == "__main__":
    main()


