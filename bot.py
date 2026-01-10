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

# OpenAI SDK (новый стиль)
from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ainexus-bot")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# Создаём клиента только если ключ задан — иначе бот работает в режиме echo
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "AInexus запущен ✅\n\n"
        "Напиши сообщение — отвечу.\n"
        "Если OpenAI-ключ не задан, отвечаю в режиме эхо."
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return

    # 1) Если OpenAI не подключён — просто эхо
    if client is None:
        await update.message.reply_text(f"Ты написал: {text}")
        return

    # 2) OpenAI подключён — отвечаем “умно”
    try:
        # Небольшая индикация набора текста
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты дружелюбный помощник Telegram-бота AInexus. Отвечай кратко и по делу."},
                {"role": "user", "content": text},
            ],
            temperature=0.6,
            max_tokens=500,
        )

        answer = (resp.choices[0].message.content or "").strip()
        if not answer:
            answer = "Пустой ответ от модели. Попробуй переформулировать вопрос."

        await update.message.reply_text(answer)

    except Exception as e:
        # На всякий случай не падаем: логируем и отвечаем эхо
        logger.exception("OpenAI error: %s", e)
        await update.message.reply_text(
            "Сейчас не получилось достучаться до OpenAI. "
            "Я отвечу в режиме эхо:\n\n"
            f"Ты написал: {text}"
        )


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()


