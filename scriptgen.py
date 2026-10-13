"""Gemini picks one 100%-free item and writes the Hindi voice lines. Everything shown on screen (repo name, stars,
language...) comes from the real source data, never from Gemini."""
import json
import re
import requests
from config import GEMINI_API_KEY, GEMINI_MODEL
import history

PROMPT = """तुम एक Instagram चैनल "{channel}" के स्क्रिप्ट राइटर हो। चैनल पर सिर्फ़ 100% फ्री AI चीज़ें आती हैं:
फ्री/ओपन-सोर्स टूल, मॉडल, पाइपलाइन। ऑडियंस: भारत के आम लोग जिन्हें इनके बारे में पता नहीं। वीडियो में आवाज़ (पुरुष, हिंदी)
सुनाई देगी और स्क्रीन पर अंग्रेज़ी टेक्स्ट दिखेगा। वीडियो दिखाता है कि इसे Hugging Face/GitHub पर कैसे ढूँढें और चलाएँ।

नीचे आज के कैंडिडेट हैं (index, source, text). इनमें से सिर्फ़ ONE चुनो जो:
- पूरी तरह फ्री या ओपन-सोर्स हो (फ्री ट्रायल, फ्री लिमिट के बाद पेमेंट, क्रेडिट वाला = NOT free)
- नया और आम आदमी को कम पता हो, और 30 सेकंड में समझाया जा सके
अगर कोई भी clearly फ्री नहीं है तो is_100_percent_free=false रखो।

सख़्त नियम:
1. सिर्फ़ कैंडिडेट के text में दी गई जानकारी इस्तेमाल करो। कोई फ़ीचर, कीमत या हार्डवेयर ज़रूरत अपने मन से मत गढ़ो।
2. "..._say" वाली सारी लाइनें देवनागरी में बोलचाल की हिंदी में लिखो और हर अंग्रेज़ी शब्द/नाम देवनागरी में वैसे लिखो जैसे बोला जाता है
   (जैसे: गिटहब, हगिंग फेस, ओपन सोर्स, एआई, क्वेन थ्री)। लैटिन अक्षर बिलकुल नहीं, क्योंकि आवाज़ उन्हें गलत पढ़ती है।
3. "..._show" और "..._lead" सिर्फ़ अंग्रेज़ी (ASCII) में, और बहुत छोटे।
4. शब्द-सीमा सख़्ती से मानो (कुल लगभग 80 शब्द)।
5. PC/GPU की ज़रूरत text से साफ़ न हो तो: मॉडल/GitHub रिपो = "pc", वेब डेमो Space = "mobile"।

सिर्फ़ JSON दो:
{{
 "pick": <index>,
 "is_100_percent_free": true/false,
 "free_reason": "क्यों फ्री है (एक लाइन, हिंदी)",
 "category": "tool" | "pipeline" | "model",
 "platform": "pc" | "mobile" | "both",
 "tool_name": "नाम (English)",
 "hook_say": "हिंदी हुक, 8 शब्द तक, 'फ्री' ज़रूर, जैसे 'ये एआई बिल्कुल फ्री है और किसी को पता नहीं'",
 "hook_lead": "छोटा अंग्रेज़ी शब्द (2-3 words), जैसे 'Nobody knows'",
 "hook_show": "अंग्रेज़ी, 2-3 शब्द, जैसे '100% FREE AI'",
 "intro_say": "इसका नाम बताओ और एक लाइन, 12 शब्द तक",
 "what_say": "ये क्या करता है, 16 शब्द तक",
 "what_lead": "1-2 अंग्रेज़ी शब्द, जैसे 'it can'",
 "what_show": "अंग्रेज़ी 2-4 शब्द, जैसे 'MAKES VIDEOS FROM TEXT'",
 "step1_say": "पहले साइट खोलने को कहो (Hugging Face या GitHub, जो सही हो), 8 शब्द तक",
 "step2_say": "सर्च में नाम लिखने को कहो, 10 शब्द तक",
 "step3_say": "फिर इसे फ्री में चलाने/डाउनलोड करने को कहो, 12 शब्द तक",
 "plat_say": "PC पर चलेगा या मोबाइल पर भी, 8 शब्द तक",
 "cta_say": "रोज़ नया फ्री एआई के लिए फॉलो करो और पूरा गाइड चाहिए तो कमेंट में गाइड लिखो, 14 शब्द तक",
 "caption": "Instagram कैप्शन हिंदी में, 3-4 लाइन, आख़िर में: पूरा गाइड चाहिए? कमेंट करो GUIDE",
 "hashtags": ["#freeai", ...8 तक],
 "guide": "पूरा स्टेप-बाई-स्टेप गाइड हिंदी में: क्या है, कहाँ मिलेगा (लिंक), कैसे चलाएँ, PC में क्या चाहिए, ध्यान देने की बातें"
}}

कैंडिडेट:
{cands}
"""


def _pool(items, per_source=6):
    primary = [i for i in items if i.get("meta")]  # HF / GitHub items: real repo cards can be shown
    rest = [i for i in items if not i.get("meta")]
    pick = primary if len(primary) >= 3 else primary + rest
    by = {}
    for it in pick:
        by.setdefault(it["source"], []).append(it)
    pool = []
    for lst in by.values():
        pool += lst[:per_source]
    return pool


def _gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    r = requests.post(url, params={"key": GEMINI_API_KEY}, timeout=90, json={
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"}})
    r.raise_for_status()
    txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip()).strip()
    return json.loads(txt)


def fallback_script(item):
    """Only when no Gemini key is set, so the app still produces a test video."""
    site = "हगिंग फेस" if (item.get("meta") or {}).get("site") == "hf" else "गिटहब"
    return {"pick": 0, "is_100_percent_free": False, "free_reason": "GEMINI_API_KEY नहीं है, जाँच नहीं हुई",
            "category": item["kind"] if item["kind"] in ("tool", "model", "pipeline") else "tool",
            "platform": "mobile" if "Space" in item["source"] else "pc", "tool_name": item["title"].split("/")[-1][:30],
            "hook_say": "ये एआई बिल्कुल फ्री है", "hook_lead": "Nobody knows", "hook_show": "100% FREE AI",
            "intro_say": "आज का फ्री एआई टूल देखो", "what_say": "ये आज का नया फ्री टूल है", "what_lead": "it is", "what_show": "NEW AND FREE",
            "step1_say": f"पहले {site} खोलो", "step2_say": "सर्च में ये नाम लिखो", "step3_say": "और इसे फ्री में चलाओ",
            "plat_say": "ये मोबाइल पर भी चलेगा" if "Space" in item["source"] else "ये पीसी पर चलेगा", "cta_say": "रोज़ नया फ्री एआई के लिए फॉलो करो, गाइड चाहिए तो कमेंट करो",
            "caption": f"आज का फ्री AI: {item['title']}\nपूरा गाइड चाहिए? कमेंट करो GUIDE",
            "hashtags": ["#freeai", "#aitools", "#opensource"],
            "guide": f"{item['title']}\n{item['url']}\n(Gemini key जोड़ने पर पूरा गाइड बनेगा)"}


def make_script(items, channel, log=print, tries=3):
    pool = _pool(items)
    if not pool:
        raise RuntimeError("कोई नया कैंडिडेट नहीं मिला (सब सोर्स फेल या सब पहले इस्तेमाल हो चुके)")
    if not GEMINI_API_KEY:
        log("⚠ GEMINI_API_KEY नहीं है — टेस्ट स्क्रिप्ट बन रही है")
        return pool[0], fallback_script(pool[0])
    for _ in range(tries):
        cands = "\n".join(f"[{i}] ({c['source']}) {c['text'][:260]}" for i, c in enumerate(pool))
        data = _gemini(PROMPT.format(channel=channel, cands=cands))
        if isinstance(data, list):
            data = data[0]
        try:
            item = pool[int(data["pick"])]
        except Exception:
            log("✘ Gemini ने गलत index दिया, दोबारा")
            continue
        if data.get("is_100_percent_free") is True:
            return item, data
        log(f"⏭ फ्री पक्का नहीं: {item['title'][:50]} — छोड़ा")
        history.mark(item["id"], "SKIPPED not-free: " + item["title"])
        pool = [c for c in pool if c["id"] != item["id"]]
        if not pool:
            break
    raise RuntimeError("आज कोई पक्का-फ्री आइटम नहीं मिला। थोड़ी देर बाद दोबारा चलाओ।")


def ascii_show(text, max_words=4):
    t = re.sub(r"[^A-Za-z0-9%&+'!?.\- ]", " ", str(text or ""))
    return " ".join(t.split()[:max_words]).upper()


def ascii_lead(text, max_words=3):
    t = re.sub(r"[^A-Za-z0-9%&+'!?.\- ]", " ", str(text or ""))
    return " ".join(t.split()[:max_words])


def beats_from(script, item):
    """The 8 beats of every video. 'say' is spoken, 'show' is the big English text, 'visual' says what is drawn."""
    meta = item.get("meta") or {}
    has_repo = bool(meta.get("repo"))
    site = meta.get("site", "")
    src = item["id"].split(":")[0]
    plat = script.get("platform") if script.get("platform") in ("pc", "mobile", "both") else "pc"
    open_show = {"hf": "OPEN HUGGING FACE", "gh": "OPEN GITHUB"}.get(site, "OPEN THE LINK")
    run_show = {"hfs": "TRY IT FREE", "hfm": "DOWNLOAD IT FREE", "gh": "CLONE AND RUN"}.get(src, "TRY IT FREE")
    plat_show = {"pc": "PC ONLY", "mobile": "WORKS ON MOBILE", "both": "PC AND MOBILE"}[plat]
    name_show = ascii_show(script.get("tool_name") or meta.get("repo", "").split("/")[-1], 3) or "NEW AI"
    g = script.get
    return [
        {"id": "hook", "say": g("hook_say", "ये एआई बिल्कुल फ्री है"), "show": ascii_show(g("hook_show"), 3) or "100% FREE AI",
         "lead": ascii_lead(g("hook_lead", "Nobody knows")), "visual": "none", "echo": True},
        {"id": "intro", "say": g("intro_say", ""), "show": name_show, "lead": "meet",
         "visual": "card" if has_repo else "none"},
        {"id": "what", "say": g("what_say", ""), "show": ascii_show(g("what_show"), 4) or "NEW AND FREE",
         "lead": ascii_lead(g("what_lead", "it can"), 2), "visual": "none"},
        {"id": "step1", "say": g("step1_say", ""), "show": open_show, "lead": "", "visual": "site", "step": 1, "site": site},
        {"id": "step2", "say": g("step2_say", ""), "show": "SEARCH THIS NAME", "lead": "",
         "visual": "search" if has_repo else "site", "step": 2, "site": site},
        {"id": "step3", "say": g("step3_say", ""), "show": run_show, "lead": "",
         "visual": "click" if has_repo else "none", "step": 3},
        {"id": "plat", "say": g("plat_say", ""), "show": plat_show, "lead": "", "visual": "plat", "plat": plat},
        {"id": "cta", "say": g("cta_say", ""), "show": "COMMENT GUIDE", "lead": "want it all?", "visual": "comment"},
    ]


def beats_to_text(beats):
    return "\n".join(f"{b['say']} | {b['show']} | {b.get('lead', '')}" for b in beats)


def apply_text(beats, text):
    """Edit panel: one line per beat → 'हिंदी बोल | ENGLISH SHOW | lead'. Visuals stay as they were."""
    lines = [l for l in (text or "").splitlines() if l.strip()]
    out = []
    for i, b in enumerate(beats):
        nb = dict(b)
        if i < len(lines):
            parts = [p.strip() for p in lines[i].split("|")]
            nb["say"] = parts[0] or b["say"]
            if len(parts) > 1 and ascii_show(parts[1]):
                nb["show"] = ascii_show(parts[1], 5)
            if len(parts) > 2:
                nb["lead"] = ascii_lead(parts[2])
        out.append(nb)
    return out
