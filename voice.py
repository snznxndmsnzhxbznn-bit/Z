"""Male Hindi voice, one clip per beat. Each beat's on-screen duration = its audio length, so voice and
visuals are in sync by construction (nothing is guessed or matched afterwards)."""
import asyncio
import base64
import hashlib
import os
import subprocess
import time
import requests
import config

LEAD, TAIL = 0.12, 0.28  # silence before / after each spoken line


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True)
    return float(out.stdout.strip())


def _edge(text, out, rate_pct):
    import edge_tts

    async def go():
        await edge_tts.Communicate(text, config.EDGE_VOICE, rate=f"{rate_pct:+d}%").save(out)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(go())
    finally:
        loop.close()


def _gemini(text, out, rate_pct):
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY नहीं है")
    pace = " Speak a little faster." if rate_pct > 8 else ""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_TTS_MODEL}:generateContent"
    body = {"contents": [{"parts": [{"text": "Say this in Hindi, in an energetic male tech-YouTuber voice." + pace + "\n" + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": config.GEMINI_TTS_VOICE}}}}}
    r = requests.post(url, params={"key": config.GEMINI_API_KEY}, json=body, timeout=90)
    r.raise_for_status()
    pcm = base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", "pipe:0", out],
                   input=pcm, check=True)


def _fake(text, out, rate_pct):
    """Tone whose length follows the text. ONLY for testing sync without network."""
    d = max(0.8, len(text) * 0.075 / (1 + rate_pct / 100))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=f=190:d={d:.3f}", "-af", "volume=0.15", out], check=True)


ENGINES = {"edge": (_edge, "mp3"), "gemini": (_gemini, "wav"), "fake": (_fake, "wav")}


def clip(text, rate_pct=0, log=print):
    text = " ".join(text.split())
    if not text:
        raise RuntimeError("खाली वाक्य — बोलने के लिए कुछ लिखो")
    os.makedirs(config.VOICE_CACHE, exist_ok=True)
    order = {"auto": ["edge", "gemini"]}.get(config.VOICE_ENGINE, [config.VOICE_ENGINE])
    errs = []
    for name in order:
        fn, ext = ENGINES[name]
        key = hashlib.sha1(f"{name}|{config.EDGE_VOICE}|{config.GEMINI_TTS_VOICE}|{rate_pct}|{text}".encode()).hexdigest()[:20]
        path = os.path.join(config.VOICE_CACHE, f"{key}.{ext}")
        if os.path.exists(path):
            return path
        try:
            fn(text, path, rate_pct)
            if os.path.exists(path) and os.path.getsize(path) > 500:
                return path
            errs.append(f"{name}: खाली ऑडियो")
        except Exception as e:
            errs.append(f"{name}: {type(e).__name__}: {str(e)[:90]}")
            log(f"✘ वॉइस ({name}) फेल: {str(e)[:90]}")
    raise RuntimeError("वॉइस नहीं बनी — " + " | ".join(errs))


def synthesize(beats, target, log=print):
    """Fills beat['dur'] and beat['audio'], returns one padded voice track (wav) matching the video length."""
    rate = 0
    for attempt in range(2):
        for b in beats:
            b["_clip"] = clip(b["say"], rate, log)
            b["_adur"] = duration(b["_clip"])
        total = sum(max(b["_adur"] + LEAD + TAIL, 1.4) for b in beats)
        if attempt == 0 and total > target * 1.08 and config.VOICE_ENGINE != "fake":
            rate = min(30, int((total / target - 1) * 100) + 3)
            log(f"⏩ वॉइस {total:.0f}s की है, {rate}% तेज़ करके दोबारा बना रहा हूँ")
            continue
        break
    log(f"🎙 वॉइस तैयार: कुल {total:.1f} सेकंड")
    os.makedirs(config.OUT_DIR, exist_ok=True)
    stamp = int(time.time() * 1000)
    parts = []
    for i, b in enumerate(beats):
        b["dur"] = max(b["_adur"] + LEAD + TAIL, 1.4)
        wav = os.path.join(config.OUT_DIR, f"seg_{stamp}_{i}.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", b["_clip"], "-af",
                        f"adelay={int(LEAD * 1000)}:all=1,apad=whole_dur={b['dur']:.3f}", "-ar", "44100", "-ac", "1",
                        "-t", f"{b['dur']:.3f}", wav], check=True)
        parts.append(wav)
    lst = os.path.join(config.OUT_DIR, f"list_{stamp}.txt")
    with open(lst, "w") as f:
        f.write("\n".join(f"file '{p}'" for p in parts))
    track = os.path.join(config.OUT_DIR, f"voice_{stamp}.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", track], check=True)
    for p in parts + [lst]:
        os.remove(p)
    return track
