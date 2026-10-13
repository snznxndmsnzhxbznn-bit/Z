import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def _api(method, **kw):
    r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}", timeout=180, **kw)
    if not r.ok:
        raise RuntimeError(f"Telegram {method}: {r.status_code} {r.text[:160]}")
    return r.json()


def send(video_path, caption, guide):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return "⚠ TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID Secrets में नहीं हैं"
    with open(video_path, "rb") as f:
        _api("sendVideo", data={"chat_id": TELEGRAM_CHAT_ID, "caption": (caption or "")[:1000], "supports_streaming": "true"},
             files={"video": f})
    text = "📘 पूरा गाइड (कमेंट में GUIDE माँगने वालों को भेजने के लिए):\n\n" + (guide or "")
    for i in range(0, len(text), 3900):
        _api("sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": text[i:i + 3900], "disable_web_page_preview": "true"})
    return "✅ Telegram पर भेज दिया"
