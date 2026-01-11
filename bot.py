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

from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ainexus")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# ===== Анти-абьюз настройки =====
RATE_LIMIT_SECONDS = 3          # минимум 1 сообщение раз в N секунд
FLOOD_COOLDOWN_SECONDS = 10     # текст для пользователя, если флудит
DAILY_LIMIT = 10                # умных ответов в день на пользователя

# Показывать остаток только когда осталось <= N
SHOW_REMAINING_WHEN_AT_OR_BELOW = 3

# ===== Память в RAM (после рестарта Render обнуляется) =====
_last_msg_ts = {}  # user_id -> timestamp последнего сообщения (float)
_daily_usage = defaultdict(lambda: {"date": None, "count": 0})  # user_id -> {date, count}

# OpenAI client (создаём только если ключ задан)
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def today_key_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_rate_limit(user_id: int) -> bool:
    """True = можно обрабатывать, False = слишком часто."""
    now = time.time()
    last = _last_msg_ts.get(user_id, 0.0)
    if now - last < RATE_LIMIT_SECONDS:
        return False
    _last_msg_ts[user_id] = now
    return True


def ensure_daily_bucket(user_id: int) -> None:
    today = today_key_utc()
    rec = _daily_usage[user_id]
    if rec["date"] != today:
        rec["date"] = today
        rec["count"] = 0


def can_use_daily(user_id: int) -> bool:
    ensure_daily_bucket(user_id)
    return _daily_usage[user_id]["count"] < DAILY_LIMIT


def increment_daily(user_id: int) -> None:
    ensure_daily_bucket(user_id)
    _daily_usage[user_id]["count"] += 1


def decrement_daily(user_id: int) -> None:
    ensure_daily_bucket(user_id)
    if _daily_usage[user_id]["count"] > 0:
        _daily_usage[user_id]["count"] -= 1


def remaining_today(user_id: int) -> int:
    ensure_daily_bucket(user_id)
    return max(0, DAILY_LIMIT - _daily_usage[user_id]["count"])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "AInexus запущен ✅\n\n"
        f"Лимиты: 1 сообщение / {RATE_LIMIT_SECONDS} сек, "
        f"{DAILY_LIMIT} умных ответов в день.\n\n"
        "Напиши сообщение — отвечу."
    )


async def echo_or_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    user_id = msg.from_user.id if msg.from_user else 0
    text = msg.text.strip()

    # 1) Анти-флуд (не зовём OpenAI)
    if user_id and not check_rate_limit(user_id):
        await msg.reply_text(f"⏳ Слишком часто. Подожди {FLOOD_COOLDOWN_SECONDS} сек.")
        return

    # 2) Если OpenAI не подключён — эхо (лимит не тратим)
    if client is None:
        await msg.reply_text(f"Ты написал: {text}\n\n⚠️ OpenAI-ключ не задан — режим эхо.")
        return

    # 3) Проверяем дневной лимит ДО вызова OpenAI
    if not can_use_daily(user_id):
        await msg.reply_text(
            f"🚫 Лимит на сегодня исчерпан ({DAILY_LIMIT}/день).\n"
            "Попробуй завтра или подключи тариф."
        )
        return

    # 4) Вызываем OpenAI: списываем лимит, но откатываем при ошибке
    increment_daily(user_id)
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты помощник AInexus. Отвечай по-русски, кратко и по делу."},
                {"role": "user", "content": text},
            ],
            temperature=0.6,
            max_tokens=500,
        )

        answer = (resp.choices[0].message.content or "").strip()
        if not answer:
            answer = "Похоже, получился пустой ответ. Попробуй переформулировать вопрос."

        await msg.reply_text(answer)

    except Exception as e:
        # При любой ошибке OpenAI — НЕ списываем дневной лимит
        decrement_daily(user_id)
        logger.exception("OpenAI error: %s", e)
        await msg.reply_text(
            "⚠️ OpenAI сейчас недоступен или закончилась квота.\n"
            "Лимит на сегодня не списан. Попробуй позже."
        )
        return

    # 5) Показываем остаток ТОЛЬКО когда осталось мало
    rem = remaining_today(user_id)
    if rem <= SHOW_REMAINING_WHEN_AT_OR_BELOW:
        await msg.reply_text(f"ℹ️ Осталось умных ответов сегодня: {rem}")


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_or_ai))

    logger.info("Bot started (polling).")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
