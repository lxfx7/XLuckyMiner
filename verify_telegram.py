import sys
import os
import logging

# Add current directory to path so we can import modules
sys.path.append(os.getcwd())

try:
    import telegram_config as tg_config
    from miner.telegram_sender import TelegramSender
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)



# Setup Logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "logtest_verify_telegram.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def verify_telegram():
    logging.info("Testing Telegram Integration...")
    
    if not hasattr(tg_config, 'TELEGRAM_BOT_TOKEN') or tg_config.TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":

        logging.error("❌ Error: Telegram config not set. Please edit telegram_config.py")
        return

    sender = TelegramSender(tg_config.TELEGRAM_BOT_TOKEN, tg_config.TELEGRAM_CHAT_ID)
    
    if not sender.enabled:
         logging.error("❌ Error: Telegram Sender disabled (check logs above).")
         return

    logging.info(f"Sending test message to Chat ID: {tg_config.TELEGRAM_CHAT_ID}...")
    if sender.send_message("🔔 This is a verified TEST message from XLuckyMiner verification."):
        logging.info("✅ Message sent successfully. Check your Telegram!")
    else:
        logging.error("❌ Failed to send message. Check the error log above.")

if __name__ == "__main__":
    verify_telegram()
