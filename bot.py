import os
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --- OpenAI ---
from openai import OpenAI
from openai import APIError, RateLimitError, AuthenticationError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AInexus")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Render для Web Service ожидает открытый порт:
PORT = int(os.getenv("PORT", "10000"))

# OpenAI client (создаём только если ключ есть)
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ----------------- Mini HTTP server (для Render) -----------------

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


def run_http_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        logger.info(f"HTTP server started on 0.0.0.0:{PORT} (/, /healthz)")
        server.serve_forever()
    except Exception as e:
        logger.exception(f"HTTP server failed: {e}")


# ----------------- OpenAI helper -----------------

def ask_openai(user_text: str) -> str:
    """
    Возвращает текст ответа от OpenAI.
    Важно: при ошибках НЕ падаем, а возвращаем понятное сообщение.
    """
    if not client:
        return "⚠️ OpenAI-ключ не задан — работаю в режиме эхо."

    try:
        resp = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "system",
                    "content": (
                        "Ты — помощник бота AInexus. Отвечай кратко, по делу, на русском. "
                        "Если вопрос непонятен — уточни."
                    ),
                },
                {"role": "user", "content": user_text},
            ],
        )

        # Универсально достаем текст
        text = getattr(resp, "output_text", "") or ""
        text = text.strip()
        return text if text else "⚠️ Пустой ответ от модели. Попробуй переформулировать."

    except AuthenticationError:
        return "❌ OpenAI-ключ неверный или отозван. Проверь OPENAI_API_KEY в Render."
    except RateLimitError:
        # сюда попадает и 429, и insufficient_quota в некоторых случаях
        return "⚠️ OpenAI временно недоступен (лимит/квота). Попробуй позже."
    except APIError as e:
        # 5xx/4xx от OpenAI (кроме auth/ratelimit)
        logger.exception(f"OpenAI APIError: {e}")
        return "⚠️ Ошибка OpenAI. Попробуй чуть позже."
    except Exception as e:
        logger.exception(f"OpenAI unexpected error: {e}")
        return "⚠️ Не удалось получить ответ от OpenAI. Попробуй позже."


# ----------------- Telegram handlers -----------------

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
        "2) Я отвечу.\n\n"
        "Команды:\n"
        "/start — запуск\n"
        "/tariffs — тарифы и лимиты\n"
        "/privacy — безопасность и политика\n"
        "/support — связь\n"
    )


async def tariffs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Тарифы и лимиты (временно):\n"
        "— Тестовый режим.\n"
        "— Лимиты и тарифы настроим после финального теста OpenAI.\n"
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


async def echo_or_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return

    # Если ключа OpenAI нет — echo
    if not OPENAI_API_KEY:
        await update.message.reply_text(f"Ты написал: {text}\n\n⚠️ OpenAI-ключ не задан — работаю в режиме эхо.")
        return

    # Реальный ответ от OpenAI (без падений)
    answer = ask_openai(text)
    await update.message.reply_text(answer)


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")

    # 1) Поднимаем порт для Render (в фоне)
    threading.Thread(target=run_http_server, daemon=True).start()

    # 2) Запускаем Telegram polling
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("tariffs", tariffs))
    app.add_handler(CommandHandler("privacy", privacy))
    app.add_handler(CommandHandler("support", support))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_or_ai))

    logger.info("Telegram bot starting (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()

