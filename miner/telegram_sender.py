import requests
import json
import logging


# Telegram rejects anything longer than 4096 characters.
MAX_MESSAGE_LENGTH = 4000


class TelegramSender:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.enabled = bool(token and chat_id and token != "YOUR_BOT_TOKEN_HERE")
        if not self.enabled:
            print("Telegram notification disabled (missing config).")

    def send_message(self, text, parse_mode="Markdown"):
        """Sends a message to the configured Telegram chat."""
        if not self.enabled:
            return False

        if len(text) > MAX_MESSAGE_LENGTH:
            text = text[:MAX_MESSAGE_LENGTH] + "\n[...truncated]"

        try:
            payload = {"chat_id": self.chat_id, "text": text}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            response = requests.post(self.base_url, json=payload, timeout=10)
            if response.status_code == 400 and parse_mode:
                # Crash alerts carry tracebacks, whose stray _ * ` characters are
                # invalid Markdown. Resend as plain text so the alert still lands.
                return self.send_message(text, parse_mode=None)
            if response.status_code != 200:
                print(f"Failed to send Telegram message: {response.text}")
                return False
            return True
        except Exception as e:
            print(f"Error sending Telegram message: {e}")
            return False

if __name__ == "__main__":
    # Test
    # Load config manually for test
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    try:
        from telegram import config
        sender = TelegramSender(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
        sender.send_message("Test message from TelegramSender module.")
    except ImportError:
        print("Config not found for test.")
