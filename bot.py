import os
import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# OpenAI SDK (новый)
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Создаём клиента только если ключ задан
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "AInexus запущен ✅\n\nНапиши сообщение — отвечу.\n"
        "Если OpenAI-ключ не задан, я отвечаю в режиме эхо."
    )


def _safe_trim(text: str, limit: int = 3500) -> str:
    """Telegram ограничивает длину сообщений, режем безопасно."""
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "…"


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = (update.message.text or "").strip()
    if not user_text:
        return

    # Если ключа нет — работаем как раньше, без падений
    if client is None:
        await update.message.reply_text(f"Ты написал: {user_text}\n\n(OPENAI_API_KEY не задан)")
        return

    try:
        # Самый простой вызов: один запрос → один ответ
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты — дружелюбный помощник Telegram-бота. Отвечай кратко и по делу."},
                {"role": "user", "content": user_text},
            ],
            temperature=0.7,
        )

        answer = resp.choices[0].message.content or "Пустой ответ."
        await update.message.reply_text(_safe_trim(answer))

    except Exception as e:
        logger.exception("OpenAI error: %s", e)
        await update.message.reply_text(
            "⚠️ OpenAI сейчас недоступен. Я живой, просто ИИ не ответил.\n"
            "Попробуй ещё раз через минуту."
        )


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения TELELEGRAM_BOT_TOKEN/TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.run_polling()


if __name__ == "__main__":
    main()

