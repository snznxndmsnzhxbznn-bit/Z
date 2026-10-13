"""Font loader. Big text uses Anton (condensed poster font) + Great Vibes (script). They are downloaded once
from Google Fonts' GitHub repo; you can also drop the .ttf files into a `fonts/` folder in the Space.
If nothing can be downloaded, DejaVu fallbacks are used so the video still renders."""
import os
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DIRS = [os.path.join(HERE, "fonts"), "/tmp/fonts"]
RAW = "https://github.com/google/fonts/raw/main/ofl/"
SPECS = {
    "display": ("Anton-Regular.ttf", RAW + "anton/Anton-Regular.ttf"),
    "script": ("GreatVibes-Regular.ttf", RAW + "greatvibes/GreatVibes-Regular.ttf"),
}
DJ = "/usr/share/fonts/truetype/dejavu/"
FALLBACK = {
    "display": [DJ + "DejaVuSansCondensed-Bold.ttf", DJ + "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"],
    "script": [DJ + "DejaVuSerif-BoldItalic.ttf", DJ + "DejaVuSerifCondensed-BoldItalic.ttf", DJ + "DejaVuSans-Bold.ttf"],
    "ui_bold": [DJ + "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"],
    "ui": [DJ + "DejaVuSans.ttf", "/usr/share/fonts/truetype/freefont/FreeSans.ttf"],
}
_failed, _cache = set(), {}


def _download(role):
    name, url = SPECS[role]
    if role in _failed:
        return None
    try:
        os.makedirs(DIRS[1], exist_ok=True)
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        dest = os.path.join(DIRS[1], name)
        with open(dest, "wb") as f:
            f.write(r.content)
        return dest
    except Exception:
        _failed.add(role)
        return None


def path(role):
    if role in _cache:
        return _cache[role]
    found = None
    if role in SPECS:
        for d in DIRS:
            p = os.path.join(d, SPECS[role][0])
            if os.path.exists(p):
                found = p
                break
        found = found or _download(role)
    if not found:
        found = next((p for p in FALLBACK.get(role, []) if os.path.exists(p)), None)
    _cache[role] = found
    return found


def using_fallback():
    return {r: (path(r) or "").split("/")[-1] for r in ("display", "script")}
