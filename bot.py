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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AInexus")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Render для Web Service ожидает открытый порт:
PORT = int(os.getenv("PORT", "10000"))


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
        # чтобы не засорять логи Render
        return


def run_http_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        logger.info(f"HTTP server started on 0.0.0.0:{PORT} (health endpoints: /, /healthz)")
        server.serve_forever()
    except Exception as e:
        logger.exception(f"HTTP server failed: {e}")


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
        "— Тестовый режим.\n"
        "— Лимиты и тарифы настроим после финального подключения OpenAI.\n"
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

    # Если ключа OpenAI нет — честный echo:
    if not OPENAI_API_KEY:
        await update.message.reply_text(
            f"Ты написал: {text}\n\n⚠️ OpenAI-ключ не задан — работаю в режиме эхо."
        )
        return

    # На этом шаге мы НЕ вызываем OpenAI, чтобы не ловить 429/insufficient_quota.
    await update.message.reply_text("✅ OpenAI-ключ вижу, следующий шаг — подключаем ответы от OpenAI.")


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")

    # 1) Поднимаем порт для Render (в фоне)
    t = threading.Thread(target=run_http_server, daemon=True)
    t.start()

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
