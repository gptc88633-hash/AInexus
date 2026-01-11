import os
import time
import logging
from datetime import datetime, timezone
from collections import defaultdict

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# ===== Анти-абьюз настройки =====
RATE_LIMIT_SECONDS = 3          # минимум 1 сообщение раз в N секунд
FLOOD_COOLDOWN_SECONDS = 10     # если флудит — просим подождать N секунд
DAILY_LIMIT = 10                # "умных" ответов в день на пользователя

# В памяти (на Render после рестарта сбросится)
_last_msg_ts = {}  # user_id -> float timestamp
_daily_usage = defaultdict(lambda: {"date": None, "count": 0})  # user_id -> {date, count}


def _today_key_utc() -> str:
    # Стабильно и не зависит от локального времени сервера
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _check_rate_limit(user_id: int) -> bool:
    """True = можно обрабатывать, False = слишком часто."""
    now = time.time()
    last = _last_msg_ts.get(user_id, 0.0)
    if now - last < RATE_LIMIT_SECONDS:
        return False
    _last_msg_ts[user_id] = now
    return True


def _check_and_increment_daily(user_id: int) -> tuple[bool, int]:
    """
    Возвращает (ok, remaining).
    Увеличивает счётчик только если ok=True.
    """
    today = _today_key_utc()
    rec = _daily_usage[user_id]

    if rec["date"] != today:
        rec["date"] = today
        rec["count"] = 0

    if rec["count"] >= DAILY_LIMIT:
        remaining = 0
        return False, remaining

    rec["count"] += 1
    remaining = DAILY_LIMIT - rec["count"]
    return True, remaining


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "AInexus запущен ✅\n\n"
        "Напиши сообщение — отвечу.\n"
        f"Лимиты: 1 сообщение / {RATE_LIMIT_SECONDS} сек, {DAILY_LIMIT} умных ответов/день."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/start — запуск\n"
        "/help — помощь\n\n"
        "Напиши текст — отвечу."
    )


async def echo_or_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    user_id = msg.from_user.id if msg.from_user else 0
    text = msg.text.strip()

    # 1) Rate-limit (анти-флуд): если слишком часто — не зовём OpenAI
    if user_id and not _check_rate_limit(user_id):
        await msg.reply_text(f"⏳ Слишком часто. Подожди {FLOOD_COOLDOWN_SECONDS} сек.")
        return

    # 2) Если OpenAI ключа нет — просто эхо (и не тратим дневной лимит)
    if not OPENAI_API_KEY:
        await msg.reply_text(f"Ты написал: {text}\n\n⚠️ OpenAI-ключ не задан — отвечаю в режиме эхо.")
        return

    # 3) Дневной лимит: считаем только "умные" ответы
    ok, remaining = _check_and_increment_daily(user_id)
    if not ok:
        await msg.reply_text(
            "🚫 Лимит на сегодня исчерпан (10/день).\n"
            "Попробуй завтра или подключи тариф."
        )
        return

    # 4) Тут будет вызов OpenAI (пока заглушка безопасная)
    # ВАЖНО: если OpenAI падает — желательно не сжигать лимит.
    # Для MVP оставим так; когда подключим OpenAI, я добавлю try/except
    # и откат счётчика при ошибке.

    await msg.reply_text(
        f"✅ Принято. Осталось умных ответов сегодня: {remaining}\n\n"
        f"Ты написал: {text}\n"
        "(следующий шаг — подключаем ответ OpenAI)"
    )


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_or_ai))

    logger.info("Bot started (polling).")
    app.run_polling()


if __name__ == "__main__":
    main()
