"""v3 renderer: premium poster typography (huge condensed gradient words, small script lead word, echo),
dark textured background with glow, and scenes that match what the voice says: Hugging Face / GitHub
symbols and cards, typed search bar, click, PC/mobile icon, FREE stamp. Frames go straight into ffmpeg."""
import functools
import math
import os
import re
import subprocess
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import fonts
from config import W, H, FPS, OUT_DIR, CHANNEL_NAME, THEMES

TEXT_W = 940          # width the big words are fitted to
VIS_CY = 1175         # centre of the visual area
GREEN = (34, 197, 94)


# ---------------------------------------------------------------- basics
@functools.lru_cache(maxsize=300)
def F(role, size):
    p = fonts.path(role)
    try:
        return ImageFont.truetype(p, max(8, int(size)))
    except Exception:
        return ImageFont.load_default()


def ease_out(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def ease_back(t):
    t = min(max(t, 0.0), 1.0)
    return 1 + 3.2 * (t - 1) ** 3 + 2.2 * (t - 1) ** 2


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def human(n):
    try:
        n = float(n)
    except Exception:
        return "0"
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(int(n))


def fit_text(text, role, max_w, start, minimum=18):
    s = start
    while s > minimum and F(role, s).getlength(text) > max_w:
        s -= 2
    return F(role, s), s


def alpha_mul(tile, a):
    if a >= 0.999:
        return tile
    tile = tile.copy()
    tile.putalpha(tile.getchannel("A").point(lambda v, q=a: int(v * q)))
    return tile


def paste_c(img, tile, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0.01 or scale <= 0.01:
        return
    if abs(scale - 1) > 0.004:
        tile = tile.resize((max(1, int(tile.width * scale)), max(1, int(tile.height * scale))), Image.BILINEAR)
    tile = alpha_mul(tile, alpha)
    img.paste(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)), tile)


# ---------------------------------------------------------------- background
def glow_sprite(color, w, h, strength=120):
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a = np.clip(1 - d, 0, 1) ** 2 * strength
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3] = color[0], color[1], color[2], a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def make_bg(th, variant):
    rng = np.random.default_rng(11 + variant)
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    cx, cy = (0.35 + 0.15 * variant) % 1.0 or 0.5, 0.6
    d = np.sqrt((x - cx) ** 2 * 0.9 + (y - cy) ** 2 * 0.5)
    t = np.clip(1.15 - d * 1.9, 0, 1)[..., None] ** 1.6
    a, b = np.array(th["bg1"], np.float32), np.array(th["bg2"], np.float32)
    base = a + (b - a) * t
    base += rng.normal(0, 5.5, (H, W, 1))  # film grain / texture
    im = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")
    d2 = ImageDraw.Draw(im, "RGBA")
    ac = th["accent"]
    for k in range(3):  # thin crossing lines like the reference posters
        x0 = int(W * (0.1 + 0.35 * ((k + variant) % 3)))
        d2.line((x0, 0, x0 + int(260 * (1 - 0.7 * (k % 2))), H), fill=ac + (26,), width=2)
    return np.asarray(im)


# ---------------------------------------------------------------- big typography
def grad_line(text, size, top, bottom):
    f = F("display", size)
    l, t, r, b = f.getbbox(text)
    w, h = r - l, b - t
    m = int(size * 0.12) + 10
    mask = Image.new("L", (w + 2 * m, h + 2 * m), 0)
    ImageDraw.Draw(mask).text((m - l, m - t), text, font=f, fill=255)
    H2, W2 = h + 2 * m, w + 2 * m
    yy = np.clip((np.arange(H2)[:, None] - m) / max(h, 1), 0, 1)
    col = np.array(top, np.float32) * (1 - yy) + np.array(bottom, np.float32) * yy
    arr = np.zeros((H2, W2, 4), np.uint8)
    arr[..., :3] = np.repeat(col[:, None, :], W2, axis=1).astype(np.uint8)
    arr[..., 3] = 255
    tile = Image.fromarray(arr, "RGBA")
    tile.putalpha(mask)
    sh = Image.new("RGBA", tile.size, (0, 0, 0, 0))
    smask = mask.filter(ImageFilter.GaussianBlur(max(3, size // 28)))
    sh.putalpha(smask.point(lambda v: int(v * 0.65)))
    out = Image.new("RGBA", (W2, H2 + int(size * 0.05)), (0, 0, 0, 0))
    out.alpha_composite(sh, (0, int(size * 0.05)))
    out.alpha_composite(tile, (0, 0))
    return out, m, h


def split_lines(text):
    toks = text.upper().split()
    lines = []
    for tk in toks:
        if lines and (len(lines[-1]) <= 3 or len(tk) <= 3) and len(lines[-1]) + 1 + len(tk) <= 11:
            lines[-1] += " " + tk
        else:
            lines.append(tk)
    while len(lines) > 4:
        i = min(range(len(lines) - 1), key=lambda k: len(lines[k]) + len(lines[k + 1]))
        lines[i:i + 2] = [lines[i] + " " + lines[i + 1]]
    return lines


def build_text(beat, th, max_h):
    lines = split_lines(beat["show"] or "FREE AI")
    f100 = F("display", 100)
    sizes = [min(400, int(TEXT_W / max(f100.getlength(ln), 1) * 100)) for ln in lines]
    gap = lambda s: int(s * 0.07)

    def total(sz):
        hs = [F("display", s).getbbox(ln)[3] - F("display", s).getbbox(ln)[1] for ln, s in zip(lines, sz)]
        return sum(hs) + sum(gap(s) for s in sz[:-1])
    tot = total(sizes)
    if beat.get("echo"):
        tot += 2 * int(0.95 * (F("display", sizes[-1]).getbbox(lines[-1])[3] - F("display", sizes[-1]).getbbox(lines[-1])[1]))
    if tot > max_h:
        k = max_h / tot
        sizes = [max(40, int(s * k)) for s in sizes]
    items, y = [], 0
    for ln, s in zip(lines, sizes):
        tile, m, h = grad_line(ln, s, th["top"], th["bottom"])
        items.append({"tile": tile, "m": m, "h": h, "y": y})
        y += h + gap(s)
    block_h = y - gap(sizes[-1])
    echoes = []
    if beat.get("echo"):
        last = items[-1]
        for k in (1, 2):
            echoes.append({"tile": alpha_mul(last["tile"], 0.34 if k == 1 else 0.14), "m": last["m"], "h": last["h"],
                           "y": last["y"] + k * int(0.95 * last["h"])})
        block_h = echoes[-1]["y"] + last["h"]
    lead = None
    if beat.get("lead"):
        ls = int(min(max(items[0]["h"] * 0.5, 70), 150))
        f, ls = fit_text(beat["lead"], "script", 640, ls)
        l, t, r, b = f.getbbox(beat["lead"])
        tl = Image.new("RGBA", (r - l + 60, b - t + 60), (0, 0, 0, 0))
        dd = ImageDraw.Draw(tl)
        dd.text((30 - l + 4, 30 - t + 5), beat["lead"], font=f, fill=(0, 0, 0, 170))
        dd.text((30 - l, 30 - t), beat["lead"], font=f, fill=th["script"] + (255,))
        lead = tl.rotate(5, resample=Image.BICUBIC, expand=True)
    return {"items": items, "echoes": echoes, "block_h": block_h, "lead": lead}


# ---------------------------------------------------------------- icons & symbols (all drawn, supersampled)
def ss_canvas(size, k=4):
    return Image.new("RGBA", (size * k, size * k), (0, 0, 0, 0)), k


def hf_smiley(size):
    im, k = ss_canvas(size)
    d = ImageDraw.Draw(im)
    S = size * k
    d.ellipse((S * 0.04, S * 0.04, S * 0.96, S * 0.96), fill=(255, 210, 30), outline=(240, 150, 0), width=int(S * 0.03))
    for ex in (0.34, 0.66):
        d.ellipse((S * (ex - 0.055), S * 0.34, S * (ex + 0.055), S * 0.48), fill=(70, 45, 10))
    d.arc((S * 0.27, S * 0.38, S * 0.73, S * 0.76), 20, 160, fill=(70, 45, 10), width=int(S * 0.045))
    for hx in (0.30, 0.70):  # the two hugging hands
        d.ellipse((S * (hx - 0.13), S * 0.70, S * (hx + 0.13), S * 0.93), fill=(255, 190, 25), outline=(225, 135, 0), width=int(S * 0.02))
    return im.resize((size, size), Image.LANCZOS)


def octo(size, bg=(255, 255, 255), fg=(13, 17, 23)):
    im, k = ss_canvas(size)
    d = ImageDraw.Draw(im)
    S = size * k
    d.ellipse((S * 0.02, S * 0.02, S * 0.98, S * 0.98), fill=bg)
    d.ellipse((S * 0.2, S * 0.28, S * 0.8, S * 0.84), fill=fg)
    d.polygon([(S * 0.22, S * 0.42), (S * 0.24, S * 0.16), (S * 0.46, S * 0.32)], fill=fg)
    d.polygon([(S * 0.78, S * 0.42), (S * 0.76, S * 0.16), (S * 0.54, S * 0.32)], fill=fg)
    d.ellipse((S * 0.36, S * 0.46, S * 0.46, S * 0.56), fill=bg)
    d.ellipse((S * 0.54, S * 0.46, S * 0.64, S * 0.56), fill=bg)
    return im.resize((size, size), Image.LANCZOS)


def with_glow(tile, color, radius=36, strength=0.9):
    pad = radius * 3
    big = Image.new("RGBA", (tile.width + 2 * pad, tile.height + 2 * pad), (0, 0, 0, 0))
    a = Image.new("L", big.size, 0)
    a.paste(tile.getchannel("A"), (pad, pad))
    a = a.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(min(255, v * strength)))
    g = Image.new("RGBA", big.size, color + (0,))
    g.putalpha(a)
    big.alpha_composite(g)
    big.alpha_composite(tile, (pad, pad))
    return big


def rounded(w, h, r, fill, outline=None, width=3):
    t = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(t).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=fill, outline=outline, width=width)
    return t


def repo_card(meta, th):
    w, h = 900, 330
    card = rounded(w, h, 34, (13, 17, 23, 255), (60, 68, 77, 255), 3)
    d = ImageDraw.Draw(card)
    card.alpha_composite(octo(76), (36, 34))
    owner, _, name = meta["repo"].partition("/")
    f1, _ = fit_text(f"{owner} / {name}", "ui_bold", 690, 42)
    d.text((136, 40), f"{owner} /", font=f1, fill=(139, 148, 158))
    ow = f1.getlength(f"{owner} / ")
    d.text((136 + ow, 40), name, font=f1, fill=(240, 246, 252))
    desc = (meta.get("desc") or "").strip()
    y = 128
    if desc:
        words, line, rows = desc.split(), "", []
        fd = F("ui", 32)
        for wd in words:
            if fd.getlength((line + " " + wd).strip()) > w - 80:
                rows.append(line)
                line = wd
            else:
                line = (line + " " + wd).strip()
        rows.append(line)
        if len(rows) > 2:
            rows = rows[:2]
            rows[1] = rows[1].rstrip(".,") + "…"
        for r_ in rows:
            d.text((40, y), r_, font=fd, fill=(139, 148, 158))
            y += 44
    fy = h - 82
    d.text((40, fy), "★", font=F("ui_bold", 40), fill=(255, 200, 40))
    d.text((92, fy + 2), human(meta.get("stars", 0)), font=F("ui_bold", 38), fill=(240, 246, 252))
    x = 92 + F("ui_bold", 38).getlength(human(meta.get("stars", 0))) + 44
    if meta.get("lang"):
        d.ellipse((x, fy + 14, x + 22, fy + 36), fill=th["accent"])
        d.text((x + 34, fy + 2), meta["lang"], font=F("ui", 36), fill=(200, 208, 216))
        x += 34 + F("ui", 36).getlength(meta["lang"]) + 40
    if meta.get("license"):
        d.rounded_rectangle((x, fy + 2, x + F("ui_bold", 30).getlength(meta["license"]) + 36, fy + 48), radius=22, outline=(90, 100, 110), width=2)
        d.text((x + 18, fy + 8), meta["license"], font=F("ui_bold", 30), fill=(200, 208, 216))
    return with_glow(card, th["accent"], 38, 1.0)


def hf_card(meta, th):
    w, h = 900, 300
    card = rounded(w, h, 34, (24, 26, 36, 255), (255, 210, 30, 255), 4)
    d = ImageDraw.Draw(card)
    card.alpha_composite(hf_smiley(84), (36, 34))
    d.text((140, 36), f"Hugging Face  ·  {meta.get('type', 'Space')}", font=F("ui", 32), fill=(170, 176, 190))
    f1, _ = fit_text(meta["repo"], "ui_bold", 820, 46)
    d.text((40, 118), meta["repo"], font=f1, fill=(255, 255, 255))
    fy = h - 84
    d.text((40, fy), "♥", font=F("ui_bold", 40), fill=(255, 90, 120))
    d.text((92, fy + 2), human(meta.get("likes", 0)), font=F("ui_bold", 38), fill=(255, 255, 255))
    badge = str(meta.get("badge") or "")
    if badge:
        x = 92 + F("ui_bold", 38).getlength(human(meta.get("likes", 0))) + 44
        bw = F("ui_bold", 32).getlength(badge) + 40
        d.rounded_rectangle((x, fy + 2, x + bw, fy + 50), radius=24, fill=(255, 210, 30))
        d.text((x + 20, fy + 8), badge, font=F("ui_bold", 32), fill=(30, 22, 5))
    return with_glow(card, th["accent"], 38, 1.0)


def site_logo(kind, th):
    size = 340
    mark = hf_smiley(size) if kind == "hf" else octo(size)
    mark = with_glow(mark, (255, 200, 40) if kind == "hf" else (255, 255, 255), 44, 0.8)
    label = "huggingface.co" if kind == "hf" else "github.com"
    f = F("ui_bold", 46)
    pw = int(f.getlength(label)) + 120
    pill = rounded(pw, 100, 50, (20, 22, 30, 255), th["accent"] + (255,), 3)
    d = ImageDraw.Draw(pill)
    d.ellipse((30, 34, 62, 66), outline=th["accent"], width=4)
    d.line((60, 62, 72, 74), fill=th["accent"], width=5)
    d.text((86, 22), label, font=f, fill=(255, 255, 255))
    out = Image.new("RGBA", (max(mark.width, pw) + 20, mark.height + pill.height + 10), (0, 0, 0, 0))
    out.alpha_composite(mark, ((out.width - mark.width) // 2, 0))
    out.alpha_composite(pill, ((out.width - pw) // 2, mark.height + 10))
    return out


def search_bar(th):
    w, h = 900, 124
    t = rounded(w, h, 62, (22, 24, 33, 255), th["accent"] + (255,), 4)
    d = ImageDraw.Draw(t)
    d.ellipse((44, 38, 82, 76), outline=(200, 205, 215), width=6)
    d.line((78, 72, 96, 90), fill=(200, 205, 215), width=7)
    return with_glow(t, th["accent"], 30, 0.7)


def icon_tile(kind, th):
    S = 520
    im, k = Image.new("RGBA", (S * 2, S * 2), (0, 0, 0, 0)), 2
    d = ImageDraw.Draw(im)
    c = th["accent"] + (255,)
    lw = 22

    def pc(ox):
        d.rounded_rectangle((S + ox - 250, S - 190, S + ox + 250, S + 100), radius=34, outline=c, width=lw)
        d.line((S + ox, S + 100, S + ox, S + 190), fill=c, width=lw)
        d.line((S + ox - 120, S + 195, S + ox + 120, S + 195), fill=c, width=lw)

    def mob(ox):
        d.rounded_rectangle((S + ox - 120, S - 230, S + ox + 120, S + 210), radius=46, outline=c, width=lw)
        d.ellipse((S + ox - 16, S + 162, S + ox + 16, S + 194), fill=c)
    if kind == "pc":
        pc(0)
    elif kind == "mobile":
        mob(0)
    elif kind == "both":
        pc(-180)
        mob(300)
    elif kind == "comment":
        d.rounded_rectangle((S - 270, S - 190, S + 270, S + 100), radius=80, outline=c, width=lw)
        d.polygon([(S - 120, S + 90), (S - 200, S + 210), (S - 30, S + 90)], fill=c)
        for i in (-110, 0, 110):
            d.ellipse((S + i - 24, S - 24, S + i + 24, S + 24), fill=c)
    im = im.crop(im.getbbox())
    return with_glow(im.resize(((im.width * 13) // (k * 10), (im.height * 13) // (k * 10)), Image.LANCZOS), th["accent"], 34, 0.8)


def stamp_tile(th, text="100% FREE", size=92):
    f = F("display", size)
    l, t, r, b = f.getbbox(text)
    pw, ph = r - l + 110, b - t + 70
    s = rounded(pw, ph, 26, GREEN + (255,), (255, 255, 255, 255), 8)
    ImageDraw.Draw(s).text((55 - l, 35 - t), text, font=f, fill=(255, 255, 255))
    return with_glow(s.rotate(7, resample=Image.BICUBIC, expand=True), GREEN, 34, 0.9)


def pill(text, size, fill, fg):
    f = F("ui_bold", size)
    w, h = int(f.getlength(text)) + size * 2, int(size * 1.9)
    t = rounded(w, h, h // 2, fill + (255,))
    ImageDraw.Draw(t).text((size, h / 2 - size * 0.62), text, font=f, fill=fg)
    return t


def cursor_tile():
    t = Image.new("RGBA", (96, 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    pts = [(8, 6), (8, 92), (30, 72), (46, 108), (60, 102), (44, 68), (74, 66)]
    d.polygon(pts, fill=(255, 255, 255), outline=(0, 0, 0))
    return t


# ---------------------------------------------------------------- main
def render(beats, audio_path=None, out_path=None, theme="Gold & Dark", channel=None, progress=None):
    th = THEMES.get(theme) or list(THEMES.values())[0]
    channel = channel or CHANNEL_NAME
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = out_path or os.path.join(OUT_DIR, f"short_{int(time.time())}.mp4")
    bgs = [make_bg(th, v) for v in range(3)]
    glow_a, glow_b = glow_sprite(th["hi"], 1000, 800, 125), glow_sprite(th["accent"], 900, 700, 70)
    cursor = cursor_tile()
    top_free = pill("100% FREE", 26, GREEN, (255, 255, 255))
    stamp = stamp_tile(th)
    cache = {}

    def get(key, fn):
        if key not in cache:
            cache[key] = fn()
        return cache[key]

    prep, t0 = [], 0.0
    for b in beats:
        vis = b.get("visual", "none")
        text = build_text(b, th, 520 if vis != "none" else 700)
        p = {"b": b, "t0": t0, "dur": b["dur"], "text": text, "vis": vis}
        meta = b.get("meta") or {}
        if vis in ("card", "search", "click") and meta.get("repo"):
            p["card"] = get(("card", meta["repo"]), lambda m=meta: hf_card(m, th) if m.get("site") == "hf" else repo_card(m, th))
        elif vis in ("card", "search", "click"):
            p["vis"] = "none"
        if vis == "site":
            p["logo"] = get(("logo", b.get("site") or "gh"), lambda s=b.get("site") or "gh": site_logo("hf" if s == "hf" else "gh", th))
        if vis == "search":
            p["bar"] = get("bar", lambda: search_bar(th))
        if vis == "plat":
            p["icon"] = get(("icon", b.get("plat", "pc")), lambda k=b.get("plat", "pc"): icon_tile(k, th))
        if vis == "comment":
            p["icon"] = get(("icon", "comment"), lambda: icon_tile("comment", th))
        if b.get("step"):
            p["chip"] = pill(f"STEP {b['step']}", 34, th["accent"], (18, 18, 26))
        prep.append(p)
        t0 += b["dur"]
    total, nframes = t0, int(t0 * FPS)

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    cmd += ["-i", audio_path] if audio_path else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-t", f"{total:.3f}", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for fi in range(nframes):
            t = fi / FPS
            si = next((i for i, p in enumerate(prep) if t < p["t0"] + p["dur"]), len(prep) - 1)
            p = prep[si]
            lt, dur = t - p["t0"], p["dur"]
            exit_k = min(1.0, max(0.0, (dur - lt) / 0.14))
            img = Image.fromarray(bgs[si % 3], "RGB")
            img.paste(glow_a, (int(-250 + 500 * (0.5 + 0.5 * math.sin(t * 0.6 + si))), int(300 + 200 * math.sin(t * 0.45))), glow_a)
            img.paste(glow_b, (int(250 + 300 * math.cos(t * 0.5)), int(1050 + 200 * math.sin(t * 0.7 + si))), glow_b)
            d = ImageDraw.Draw(img, "RGBA")

            # header
            d.text((60, 104), channel, font=F("ui_bold", 40), fill=(255, 255, 255, 215))
            img.paste(top_free, (W - top_free.width - 50, 96), top_free)
            if "chip" in p:
                a = ease_out(lt / 0.25)
                paste_c(img, p["chip"], 60 + p["chip"].width / 2, 215, 1.0, a * exit_k)

            vis = p["vis"]
            vk = ease_out((lt - 0.12) / 0.3)       # visual pop progress
            vb = ease_back((lt - 0.12) / 0.4)
            vis_a = vk * exit_k
            cx, cy = W // 2, VIS_CY

            if vis == "site":
                paste_c(img, p["logo"], cx, cy, 0.6 + 0.4 * vb, vis_a)
            elif vis == "card":
                pulse = 1 + 0.012 * math.sin(t * 5)
                paste_c(img, p["card"], cx, cy, (0.6 + 0.4 * vb) * pulse, vis_a)
            elif vis == "search":
                typ_end = dur * 0.55
                paste_c(img, p["bar"], cx, cy - 240, 0.7 + 0.3 * vb, vis_a)
                q = (p["b"].get("meta") or {}).get("repo", "")
                n = int(len(q) * min(1.0, max(0.0, (lt - 0.35) / max(typ_end - 0.35, 0.1))))
                caret = "|" if int(t * 2.4) % 2 == 0 or n < len(q) else ""
                f, _ = fit_text(q + "|", "ui_bold", 690, 50)
                d.text((cx - 450 + 130, cy - 240 - 31), q[:n] + caret, font=f, fill=(255, 255, 255, int(255 * vis_a)))
                rk = (lt - dur * 0.58) / 0.3
                if rk > 0:
                    paste_c(img, p["card"], cx, cy + 130, 0.55 + 0.45 * ease_back(rk), ease_out(rk * 1.6) * exit_k)
                    mk = min(1.0, (lt - dur * 0.58) / (dur * 0.34))
                    px, py = cx + 380 - 250 * ease_out(mk), cy - 150 + 270 * ease_out(mk)
                    img.paste(cursor, (int(px), int(py)), cursor)
            elif vis == "click":
                paste_c(img, p["card"], cx, cy, 0.9 + 0.1 * vb, vis_a)
                mk = ease_out((lt - 0.25) / max(dur * 0.45, 0.1))
                px, py = cx + 420 - 330 * mk, cy + 330 - 200 * mk
                img.paste(cursor, (int(px), int(py)), cursor)
                ck = (lt - (0.25 + dur * 0.45)) / 0.35
                if 0 < ck < 1:
                    rr = 30 + 160 * ck
                    d.ellipse((px + 8 - rr, py + 6 - rr, px + 8 + rr, py + 6 + rr), outline=th["accent"] + (int(230 * (1 - ck)),), width=6)
            elif vis in ("plat", "comment"):
                paste_c(img, p["icon"], cx, cy, (0.6 + 0.4 * vb) * (1 + 0.025 * math.sin(t * 4)), vis_a)
            if p["b"].get("id") in ("plat", "cta"):
                k2 = (lt - 0.5) / 0.25
                if k2 > 0:
                    paste_c(img, stamp, cx, 1405, 1 + 0.6 * (1 - ease_out(k2)), ease_out(k2 * 1.5) * exit_k)

            # the big words
            tx = p["text"]
            top = 250 if vis != "none" else (H / 2 - tx["block_h"] / 2 - 40)
            if vis == "none":
                top = max(300, top)
            for i, it in enumerate(tx["items"]):
                k = (lt - 0.05 * i) / 0.3
                if k <= 0:
                    continue
                tile = it["tile"]
                yy = top + 60 + it["y"] - it["m"] + (1 - ease_out(k)) * 80
                sc = 1.12 - 0.12 * ease_out(k)
                if sc > 1.003:
                    tile = tile.resize((int(tile.width * sc), int(tile.height * sc)), Image.BILINEAR)
                tile = alpha_mul(tile, ease_out(k * 1.5) * exit_k)
                img.paste(tile, (int((W - tile.width) / 2), int(yy - (tile.height - it["tile"].height) / 2)), tile)
            for j, it in enumerate(tx["echoes"]):
                k = (lt - 0.28 - 0.1 * j) / 0.3
                if k <= 0:
                    continue
                yy = top + 60 + it["y"] - it["m"] + (1 - ease_out(k)) * 40
                tile = alpha_mul(it["tile"], ease_out(k) * exit_k)
                img.paste(tile, (int((W - tile.width) / 2), int(yy)), tile)
            if tx["lead"] is not None:
                k = (lt - 0.18) / 0.3
                if k > 0:
                    ld = alpha_mul(tx["lead"], ease_out(k) * exit_k)
                    ly = top + 60 - ld.height * 0.78 + (1 - ease_out(k)) * 30
                    img.paste(ld, (int(70), int(ly)), ld)

            # beat flash + progress
            if lt < 0.08:
                d.rectangle((0, 0, W, H), fill=(255, 255, 255, int(34 * (1 - lt / 0.08))))
            d.rounded_rectangle((60, 1566, W - 60, 1572), radius=3, fill=(255, 255, 255, 40))
            d.rounded_rectangle((60, 1566, 60 + (W - 120) * (t / total), 1572), radius=3, fill=th["accent"] + (255,))

            proc.stdin.write(img.tobytes())
            if progress and fi % 30 == 0:
                progress(fi / nframes)
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg failed: " + err[-400:])
    except BrokenPipeError:
        raise RuntimeError("ffmpeg बंद हो गया: " + proc.stderr.read().decode(errors="ignore")[-400:])
    return out_path
