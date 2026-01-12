import os
import json
import time
import logging
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Если openai не установлен/не нужен — бот всё равно запустится
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Анти-абьюз
MIN_SECONDS_BETWEEN_MESSAGES = 3         # 1 сообщение раз в 3 секунды
DAILY_LIMIT = 10                         # 10 сообщений в день (платных/ИИ)
FREE_MESSAGES_BEFORE_VERIFY = 2          # 2 бесплатных, потом "2+2"

DB_FILE = "db.json"


# ---------------------------
# Render Web Service: порт
# ---------------------------

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return

def start_http_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logging.info(f"HTTP health server listening on 0.0.0.0:{port}")
    server.serve_forever()


# ---------------------------
# Простая "база" (json)
# ---------------------------

def load_db() -> dict:
    if not os.path.exists(DB_FILE):
        return {"users": {}}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": {}}

def save_db(db: dict) -> None:
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"DB save failed: {e}")

def today_key() -> str:
    # день в UTC, чтобы одинаково работало на сервере
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def get_user(db: dict, user_id: int) -> dict:
    users = db.setdefault("users", {})
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "last_ts": 0.0,
            "day": today_key(),
            "daily_used": 0,
            "free_used": 0,
            "verified": False,
            "pending_math": False,
        }
    # сброс дневных лимитов при смене дня
    if users[uid].get("day") != today_key():
        users[uid]["day"] = today_key()
        users[uid]["daily_used"] = 0
        users[uid]["last_ts"] = 0.0
        users[uid]["pending_math"] = False
        # free_used и verified можно не сбрасывать ежедневно
    return users[uid]


# ---------------------------
# Команды
# ---------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "AInexus запущен ✅\n\n"
        "Напиши сообщение — отвечу.\n"
        "Команды: /help"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Как пользоваться:\n"
        "1) Просто напиши вопрос текстом.\n"
        "2) Я отвечу (если OpenAI-ключ подключен — будет ИИ-ответ).\n\n"
        "Команды:\n"
        "/start — запуск\n"
        "/tariffs — тарифы и лимиты\n"
        "/privacy — безопасность и политика\n"
        "/support — связь\n"
    )

async def tariffs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Тарифы и лимиты (временно):\n"
        f"— 2 бесплатных сообщения, потом верификация.\n"
        f"— Лимит: {DAILY_LIMIT} ИИ-сообщений в день.\n"
        f"— Анти-флуд: 1 сообщение раз в {MIN_SECONDS_BETWEEN_MESSAGES} сек.\n"
    )

async def privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Безопасность:\n"
        "— Не отправляй пароли/коды/данные карт.\n"
        "— В будущем добавим управление хранением истории.\n"
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Поддержка:\n"
        "Напиши сюда в чат, что не работает, и приложи скрин логов Render при необходимости."
    )


# ---------------------------
# Верификация "2+2"
# ---------------------------

def verification_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Я не бот ✅", callback_data="verify_start")]
    ])

async def ask_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛡 Подтверди, что ты человек.\n"
        "Нажми кнопку «Я не бот», затем ответь на вопрос 2+2.",
        reply_markup=verification_keyboard()
    )

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "verify_start":
        db = load_db()
        user = get_user(db, query.from_user.id)
        user["pending_math"] = True
        save_db(db)
        await query.message.reply_text("Вопрос: 2 + 2 = ? (просто напиши число)")
        return


# ---------------------------
# OpenAI ответ (аккуратно)
# ---------------------------

def openai_available() -> bool:
    return bool(OPENAI_API_KEY) and (OpenAI is not None)

async def get_ai_answer(prompt: str) -> tuple[str, str]:
    """
    Возвращает (status, text)
    status: "ok" | "no_key" | "temp_error" | "quota_error"
    """
    if not openai_available():
        return ("no_key", "⚠️ OpenAI-ключ не задан или библиотека OpenAI не установлена.")

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Ты полезный ассистент. Отвечай кратко и по делу на русском."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        text = resp.choices[0].message.content.strip()
        if not text:
            text = "Пустой ответ. Попробуй сформулировать иначе."
        return ("ok", text)

    except Exception as e:
        msg = str(e).lower()
        # типовые случаи: 429 / insufficient_quota / rate_limit
        if "insufficient_quota" in msg or "quota" in msg or "429" in msg or "rate limit" in msg:
            return ("quota_error", "⚠️ OpenAI сейчас недоступен (лимит/квота). Попробуй позже.")
        return ("temp_error", "⚠️ Ошибка при обращении к OpenAI. Попробуй позже.")


# ---------------------------
# Главный обработчик сообщений
# ---------------------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return

    uid = update.effective_user.id
    now = time.time()

    db = load_db()
    user = get_user(db, uid)

    # 1) анти-флуд
    if now - float(user.get("last_ts", 0.0)) < MIN_SECONDS_BETWEEN_MESSAGES:
        await update.message.reply_text("Слишком часто 🙂 Подожди 10 сек.")
        return
    user["last_ts"] = now

    # 2) если ждём ответ на 2+2
    if user.get("pending_math", False):
        if text.strip() == "4":
            user["pending_math"] = False
            user["verified"] = True
            save_db(db)
            await update.message.reply_text("✅ Отлично, верификация пройдена. Теперь можно пользоваться.")
        else:
            save_db(db)
            await update.message.reply_text("❌ Неверно. Попробуй ещё раз: 2 + 2 = ?")
        return

    # 3) 2 бесплатных сообщения → потом верификация
    if not user.get("verified", False):
        if int(user.get("free_used", 0)) >= FREE_MESSAGES_BEFORE_VERIFY:
            save_db(db)
            await ask_verification(update, context)
            return
        else:
            user["free_used"] = int(user.get("free_used", 0)) + 1
            save_db(db)
            # На бесплатном этапе можем отвечать эхо или заглушкой
            if not OPENAI_API_KEY:
                await update.message.reply_text(f"Ты написал: {text}")
            else:
                await update.message.reply_text("✅ OpenAI-ключ вижу, следующий шаг — подключаем ответы от OpenAI.")
            return

    # 4) дневной лимит (для верифицированных)
    if int(user.get("daily_used", 0)) >= DAILY_LIMIT:
        save_db(db)
        await update.message.reply_text("Лимит на сегодня исчерпан. Попробуй завтра 🙂")
        return

    # 5) Если OpenAI не подключен — эхо
    if not OPENAI_API_KEY:
        save_db(db)
        await update.message.reply_text(f"Ты написал: {text}\n\n⚠️ OpenAI-ключ не задан — работаю в режиме эхо.")
        return

    # 6) Пытаемся ответить через OpenAI.
    # ВАЖНО: дневной лимит списываем ТОЛЬКО если статус == ok.
    status, answer = await get_ai_answer(text)

    if status == "ok":
        user["daily_used"] = int(user.get("daily_used", 0)) + 1
        save_db(db)
        await update.message.reply_text(answer)
        return

    # Ошибка/квота — лимит НЕ списываем
    save_db(db)
    await update.message.reply_text(answer)


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")

    # Чтобы Render Web Service не падал по "No open ports detected"
    t = threading.Thread(target=start_http_server, daemon=True)
    t.start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("tariffs", tariffs))
    app.add_handler(CommandHandler("privacy", privacy))
    app.add_handler(CommandHandler("support", support))

    # кнопки
    app.add_handler(CallbackQueryHandler(on_callback))

    # текст
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()

if __name__ == "__main__":
    main()
