import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from logging.handlers import RotatingFileHandler
import logging
import redis
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_redis():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )


LOG_FILE = "bot.log"

logger = logging.getLogger("Bot")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# File handler (rotates at 1MB, keeps 3 backups)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
file_handler.setFormatter(formatter)

# Add handlers to logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

r = get_redis()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r.set("tracking_status", "on")
    r.publish("tracker_control", "start")
    if update.message:
        await update.message.reply_text("✅ Tracking started.")
        logger.info("Tracking started.")


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r.set("tracking_status", "off")
    r.publish("tracker_control", "stop")
    if update.message:
        await update.message.reply_text("🛑 Tracking stopped.")
        logger.info("Tracking stopped.")


async def track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        url = context.args[0]
        r.sadd("tracked_urls", url)
        if update.message:
            await update.message.reply_text(f"🔍 Now tracking: {url}")
            logger.info(f"Now tracking: {url}")
    else:
        if update.message:
            await update.message.reply_text("❗ Usage: /track <url>")


async def untrack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        url = context.args[0]
        r.srem("tracked_urls", url)
        if update.message:
            await update.message.reply_text(f"❌ Stopped tracking: {url}")
            logger.info(f"Stopped tracking: {url}")
    else:
        if update.message:
            await update.message.reply_text("❗ Usage: /untrack <url>")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    urls = r.smembers("tracked_urls")
    if not urls:
        if update.message:
            await update.message.reply_text("❗ No URLs are being tracked.")
        return
    tracking = r.get("tracking_status") or "off"
    if isinstance(tracking, bytes):
        tracking = tracking.decode("utf-8")
    message = f"🧭 Tracking: {tracking}\n🧾 URLs:\n" + "\n".join(urls)
    if update.message:
        await update.message.reply_text(message)


def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN environment variable is not set.")
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("track", track))
    application.add_handler(CommandHandler("status", status))
    application.run_polling()


if __name__ == "__main__":
    main()
