import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ℹ️ Как пользоваться", callback_data="help")],
        [InlineKeyboardButton("💳 Тарифы", callback_data="tariffs")],
        [InlineKeyboardButton("🔒 Безопасность", callback_data="privacy")],
        [InlineKeyboardButton("🆘 Поддержка", callback_data="support")],
    ])


async def send_main_menu(update: Update):
    await update.message.reply_text(
        "AInexus запущен ✅\n\n"
        "Напиши сообщение — отвечу.\n"
        "Или выбери пункт меню ниже 👇",
        reply_markup=main_menu_keyboard()
    )


# ---------- Команды ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_main_menu(update)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_main_menu(update)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Как пользоваться:\n"
        "1) Просто напиши вопрос текстом.\n"
        "2) Я отвечу (если OpenAI-ключ подключен — будет ИИ-ответ).\n\n"
        "Команды:\n"
        "/start — запуск\n"
        "/menu — меню\n"
        "/tariffs — тарифы и лимиты\n"
        "/privacy — безопасность и политика\n"
        "/support — поддержка\n"
    )


async def tariffs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Тарифы и лимиты (временно):\n"
        "— Тестовый режим.\n"
        "— Лимиты и тарифы настроим после подключения OpenAI.\n"
    )


async def privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Безопасность:\n"
        "— Не отправляй пароли/коды/данные карт.\n"
        "— Не используй бота для незаконных или опасных действий.\n"
        "— В будущем добавим управление хранением истории.\n"
    )


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Поддержка:\n"
        "Напиши сюда в чат, что не работает.\n"
        "Если нужно — приложи скрин логов Render."
    )


# ---------- Ответы ----------

async def echo_or_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return

    # Пока OpenAI может быть без баланса — чтобы бот был живым:
    if not OPENAI_API_KEY:
        await update.message.reply_text(
            f"Ты написал: {text}\n\n"
            "⚠️ OpenAI-ключ не задан или баланс не пополнен — работаю в режиме эхо."
        )
        return

    # На этом шаге пока не дергаем OpenAI, чтобы не ловить 429 и не путать тебя.
    await update.message.reply_text("✅ OpenAI-ключ вижу, следующий шаг — подключаем ответы от OpenAI.")


# ---------- Callback (кнопки) ----------

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()

    if query.data == "help":
        await query.message.reply_text(
            "Как пользоваться:\n"
            "1) Напиши вопрос текстом.\n"
            "2) Я отвечу.\n\n"
            "Команды: /help /tariffs /privacy /support"
        )
    elif query.data == "tariffs":
        await query.message.reply_text(
            "Тарифы и лимиты (временно):\n"
            "— Тестовый режим.\n"
            "— Настроим после подключения OpenAI."
        )
    elif query.data == "privacy":
        await query.message.reply_text(
            "Безопасность:\n"
            "— Не отправляй пароли/коды/данные карт.\n"
            "— Не используй бота для незаконных или опасных действий."
        )
    elif query.data == "support":
        await query.message.reply_text(
            "Поддержка:\n"
            "Напиши сюда в чат, что не работает.\n"
            "Если нужно — приложи скрин логов Render."
        )


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("tariffs", tariffs))
    app.add_handler(CommandHandler("privacy", privacy))
    app.add_handler(CommandHandler("support", support))

    # обработчик кнопок
    app.add_handler(MessageHandler(filters.COMMAND, lambda u, c: None))  # безопасно игнорируем неизвестные команды
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_or_ai))

    # CallbackQueryHandler импортировать не нужно в старых версиях? Нужно.
    # Но python-telegram-bot 21.x требует его явно — добавим:
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(on_button))

    app.run_polling()


if __name__ == "__main__":
    main()

