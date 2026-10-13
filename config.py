import os

CHANNEL_NAME = os.getenv("CHANNEL_NAME", "FREE AI DAILY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
GEMINI_TTS_VOICE = os.getenv("GEMINI_TTS_VOICE", "Charon")  # male voice
EDGE_VOICE = os.getenv("EDGE_VOICE", "hi-IN-MadhurNeural")  # male Hindi voice
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge")  # edge | gemini  (the other one is the fallback)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
DAILY_TIME = os.getenv("DAILY_TIME", "")  # HH:MM in IST, empty = scheduler off

W, H, FPS = 1080, 1920, 30
BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.getenv("OUT_DIR", "/tmp/shorts")
HISTORY_FILE = os.getenv("HISTORY_FILE", "/tmp/history.json")
FONT_DIR = os.getenv("FONT_DIR", os.path.join(BASE, "fonts"))
UA = {"User-Agent": "Mozilla/5.0 (free-ai-daily-bot)"}

# These words in a candidate's text mean it is probably not fully free -> skipped before Gemini
PAID_HINTS = ["pricing", "per month", "/month", "subscription", "freemium", "free trial",
              "premium plan", "paid plan", "enterprise plan", "credits", "start for free"]

# g_top/g_bot = gradient of the giant text, accent = lines/glow/stamps, glow = soft background light
# ---- voice (male Hindi) ----
VOICE_ENGINE = os.getenv("VOICE_ENGINE", "auto")            # auto | edge | gemini | fake(test only)
EDGE_VOICE = os.getenv("EDGE_VOICE", "hi-IN-MadhurNeural")  # male Hindi, free, no key
GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
GEMINI_TTS_VOICE = os.getenv("GEMINI_TTS_VOICE", "Charon")  # male voice
VOICE_CACHE = os.getenv("VOICE_CACHE", "/tmp/voicecache")

# top/bottom = gradient of the big text, accent = highlights/borders, hi = background glow, script = small lead word
THEMES = {
    "Gold & Dark": {"bg1": (5, 5, 7), "bg2": (34, 26, 10), "top": (255, 228, 150), "bottom": (178, 126, 28),
                    "accent": (242, 192, 62), "hi": (255, 170, 40), "script": (236, 228, 255)},
    "Pink & Dark": {"bg1": (9, 4, 9), "bg2": (66, 10, 52), "top": (255, 206, 238), "bottom": (205, 70, 150),
                    "accent": (255, 112, 192), "hi": (230, 50, 160), "script": (255, 255, 255)},
    "Purple & Dark": {"bg1": (6, 4, 15), "bg2": (38, 14, 86), "top": (228, 204, 255), "bottom": (130, 80, 236),
                      "accent": (172, 122, 255), "hi": (110, 70, 255), "script": (255, 255, 255)},
    "Ice Blue & Dark": {"bg1": (3, 8, 14), "bg2": (6, 42, 74), "top": (214, 246, 255), "bottom": (50, 170, 232),
                        "accent": (84, 212, 255), "hi": (0, 160, 255), "script": (255, 255, 255)},
}
