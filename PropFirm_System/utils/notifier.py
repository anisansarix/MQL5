import os
import logging
import json
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

def send_alert(message: str, level: str = "INFO") -> None:
    try:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        
        log_msg = f"ALERT [{level}]: {message}"
        if level == "ERROR":
            logger.error(log_msg)
        elif level == "WARNING":
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        if bot_token and chat_id:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": f"[{level}] {message}"
            }
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=5.0) as response:
                pass
    except Exception as e:
        logger.error(f"Failed to send telegram alert: {e}")
