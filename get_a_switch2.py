import requests
from bs4 import BeautifulSoup
import time
import random
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Logging setup ---
LOG_FILE = "get_a_swtich2.log"

logger = logging.getLogger("AmazonChecker")
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
AMAZON_URL = "https://www.amazon.de/Nintendo-Switch-Mario-Kart-World-Set/dp/B0F2J4SYJ2"
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


def send_telegram_message(message):
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


def is_available():
    global consecutive_failures, in_backup_mode

    try:
        response = requests.get(AMAZON_URL, headers=HEADERS, timeout=10)

        if response.status_code != 200:
            logger.warning(f"Received status code {response.status_code}")
            consecutive_failures += 1

            if consecutive_failures >= failure_threshold and not in_backup_mode:
                send_telegram_message(
                    "⚠️ Amazon check failed multiple times. Entering backup mode."
                )
                in_backup_mode = True
                time.sleep(60)

            return False

        # Recovered
        if in_backup_mode:
            send_telegram_message(
                "✅ Recovered from backup mode. Amazon is responding again."
            )
            in_backup_mode = False

        consecutive_failures = 0

        soup = BeautifulSoup(response.text, "lxml")
        if "Derzeit nicht verfügbar" in soup.text:
            logger.info("Product is NOT available.")
            return False
        else:
            logger.info("Product IS available!")
            return True

    except Exception as e:
        logger.error(f"Exception while checking product: {e}")
        consecutive_failures += 1

        if consecutive_failures >= failure_threshold and not in_backup_mode:
            send_telegram_message(
                "⚠️ Amazon check failed multiple times. Entering backup mode."
            )
            in_backup_mode = True

        return False


def main():
    while True:
        if is_available():
            send_telegram_message(
                "✅ Das Produkt ist jetzt verfügbar auf Amazon! https://www.amazon.de/Nintendo-Switch-Mario-Kart-World-Set/dp/B0F2J4SYJ2"
            )
            sys.exit(0)

        wait_time = random.uniform(20, 50)
        logger.info(f"Sleeping for {wait_time:.2f} seconds.")
        time.sleep(wait_time)


if __name__ == "__main__":
    main()
