from curl_cffi import requests, ProxySpec
import curl_cffi
from bs4 import BeautifulSoup
import time
import random
import os
import sys
import logging
import threading
from flask import Flask, jsonify
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import redis


# Load environment variables from .env file
load_dotenv()


def get_redis():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )


tracking_enabled = False

r = get_redis()
# --- Logging setup ---
LOG_FILE = "tracker.log"

logger = logging.getLogger("Tracker")
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

# --- Amazon and Telegram setup ---
# AMAZON_URL = "https://www.amazon.de/Nintendo-Switch-Mario-Kart-World-Set/dp/B0F2J4SYJ2"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

consecutive_failures = 0
failure_threshold = 3
in_backup_mode = False

app = Flask(__name__)


@app.route("/status")
def status():
    urls = r.smembers("tracked_urls")
    if not urls:
        return jsonify({"tracking": tracking_enabled, "url_count": 0})
    return jsonify({"tracking": tracking_enabled, "url_count": len(urls), "urls": urls})


def get_proxy_from_pool() -> ProxySpec | None:
    try:
        response = requests.get("http://proxy_pool:5555/get")
        if response.ok:
            proxy = response.json().get("proxy")
            return {
                "http": f"http://{proxy}",
            }
    except Exception as e:
        logger.warning(f"Could not fetch proxy from pool: {e}")
        return None


def is_product_available(url: str):
    global consecutive_failures, in_backup_mode
    bot_detection = False

    try:
        proxies = get_proxy_from_pool()
        if proxies is None:
            logger.warning("No proxy available. Skipping check.")
            return False

        response = curl_cffi.get(
            url, timeout=8, impersonate="chrome", proxies=proxies, verify=False
        )

        if response.status_code != 200:
            logger.warning(f"Received status code {response.status_code}")
            consecutive_failures += 1

            if consecutive_failures >= failure_threshold and not in_backup_mode:
                send_telegram_notification(
                    "⚠️ Amazon check failed multiple times. Entering backup mode."
                )
                in_backup_mode = True
                time.sleep(60)

            return False

        # Recovered
        if in_backup_mode:
            send_telegram_notification(
                "✅ Recovered from backup mode. Amazon is responding again."
            )
            in_backup_mode = False

        consecutive_failures = 0

        soup = BeautifulSoup(response.text, "lxml")
        if "Derzeit nicht verfügbar" in soup.text:
            logger.info("Product is NOT available.")
            return False
        elif "To discuss automated access to Amazon data" in soup.text:
            return False
            bot_detection = True
        else:
            logger.info("Product IS available!")
            return True

    except Exception as e:
        logger.error(f"Exception while checking product: {e}")
        consecutive_failures += 1

        if consecutive_failures >= failure_threshold and not in_backup_mode:
            send_telegram_notification(
                "⚠️ Amazon check failed multiple times. Entering backup mode."
            )
            in_backup_mode = True

        return False


def send_telegram_notification(message):
    url = (
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        f"?chat_id={TELEGRAM_CHAT_ID}&text={message}"
    )
    try:
        response = requests.get(url)
        response.raise_for_status()
        logger.info("Telegram message sent.")
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")


def listen_for_commands():
    global tracking_enabled
    pubsub = r.pubsub()
    pubsub.subscribe("tracker_control")

    for msg in pubsub.listen():
        if msg["type"] != "message":
            continue
        command = msg["data"]
        if command == "start":
            tracking_enabled = True
            logger.info("🔄 Tracking started via pub/sub.")
        elif command == "stop":
            tracking_enabled = False
            logger.info("⏹️ Tracking stopped via pub/sub.")


# === Main tracking loop ===
def tracker_loop():
    global tracking_enabled
    while True:
        if not tracking_enabled:
            time.sleep(2)
            continue

        urls = r.smembers("tracked_urls")
        if not urls:
            logger.info("🚫 No URLs to track. Auto-stopping.")
            tracking_enabled = False
            r.set("tracking_status", "off")
            continue
        for url in urls:
            available = is_product_available(url)
            if available:
                send_telegram_notification(f"📦 Available! {url}")
            time.sleep(random.randint(2, 4))

        time.sleep(random.randint(20, 50))


# === Entry point ===
if __name__ == "__main__":
    tracking_enabled = r.get("tracking_status") == "on"
    threading.Thread(target=listen_for_commands, daemon=True).start()
    threading.Thread(target=tracker_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
