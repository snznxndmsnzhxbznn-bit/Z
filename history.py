import json, os
from config import HISTORY_FILE


def load():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"used": []}


def used_ids():
    return set(load().get("used", []))


def mark(item_id, title=""):
    h = load()
    h.setdefault("used", []).append(item_id)
    h.setdefault("log", []).append({"id": item_id, "title": title})
    h["used"] = h["used"][-500:]
    h["log"] = h["log"][-200:]
    os.makedirs(os.path.dirname(HISTORY_FILE) or ".", exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)
