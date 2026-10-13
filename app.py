import datetime as dt
import threading
import time
import traceback

import gradio as gr

import config
import history
import pipeline
import scriptgen
import tg

THEME_NAMES = list(config.THEMES.keys())
EMPTY = ["", None, "", "", "", None, None, None]


def generate(duration, theme, send, progress=gr.Progress()):
    lines = []

    def log(m):
        print(m, flush=True)
        lines.append(str(m))
    try:
        item, s, beats, video = pipeline.run_daily(int(duration), theme, send, log=log,
                                                   progress=lambda p: progress(p, desc="वीडियो रेंडर हो रहा है"))
    except Exception as e:
        traceback.print_exc()
        lines.append(f"❌ {type(e).__name__}: {e}")
        return ["\n".join(lines)] + EMPTY[1:]
    return ["\n".join(lines), video, scriptgen.beats_to_text(beats),
            s.get("caption", "") + "\n\n" + " ".join(s.get("hashtags", [])), s.get("guide", ""), item, s, beats]


def rerender(duration, theme, beats_text, beats):
    if not beats:
        return None, "❌ पहले आज का वीडियो बनाओ"
    try:
        nb = scriptgen.apply_text(beats, beats_text)
        video = pipeline.make_video(nb, int(duration), theme)
        return video, "✅ एडिट के साथ नया वीडियो तैयार (वॉइस भी दोबारा बनी)"
    except Exception as e:
        traceback.print_exc()
        return None, f"❌ {type(e).__name__}: {e}"


def send_tg(video, caption, guide):
    if not video:
        return "❌ पहले वीडियो बनाओ"
    try:
        return tg.send(video, caption, guide)
    except Exception as e:
        return f"❌ {e}"


def show_history():
    h = history.load()
    return "\n".join(f"• {x.get('title', x.get('id'))}" for x in reversed(h.get("log", []))) or "अभी कुछ नहीं बना"


with gr.Blocks(title="Free AI Daily Studio", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎬 Free AI Daily Studio\nरोज़ का नया **100% फ्री** AI टूल → पुरुष हिंदी आवाज़ → वॉइस से सिंक वीडियो → Telegram")
    st_item, st_script, st_beats = gr.State(None), gr.State(None), gr.State(None)
    with gr.Row():
        duration = gr.Dropdown(["25", "30", "40"], value="30", label="वीडियो की लंबाई (सेकंड, लगभग)")
        theme = gr.Dropdown(THEME_NAMES, value=THEME_NAMES[0], label="रंग थीम")
        send = gr.Checkbox(value=False, label="बनते ही Telegram पर भेजो")
    go = gr.Button("🚀 आज का वीडियो बनाओ", variant="primary")
    log_out = gr.Textbox(label="लॉग", lines=6, interactive=False)
    video = gr.Video(label="वीडियो (9:16, आवाज़ के साथ)")
    with gr.Accordion("✏️ एडिट पैनल", open=True):
        beats_box = gr.Textbox(label="हर लाइन = एक सीन:   बोला जाने वाला हिंदी  |  स्क्रीन का ENGLISH टेक्स्ट  |  छोटा शब्द", lines=9)
        rr = gr.Button("🎬 एडिट के साथ दोबारा बनाओ (वॉइस भी नई बनेगी)")
    caption = gr.Textbox(label="Instagram कैप्शन + हैशटैग", lines=5)
    guide = gr.Textbox(label="पूरा गाइड (कमेंट GUIDE पर भेजने के लिए)", lines=8)
    tgb = gr.Button("📨 Telegram पर भेजो")
    status = gr.Textbox(label="स्टेटस", interactive=False)
    with gr.Accordion("📜 पिछले वीडियो", open=False):
        hb = gr.Button("हिस्ट्री दिखाओ")
        hout = gr.Textbox(lines=8, interactive=False, label="इस्तेमाल हो चुके आइटम")

    go.click(generate, [duration, theme, send], [log_out, video, beats_box, caption, guide, st_item, st_script, st_beats])
    rr.click(rerender, [duration, theme, beats_box, st_beats], [video, status])
    tgb.click(send_tg, [video, caption, guide], status)
    hb.click(show_history, None, hout)


def _scheduler():
    """Runs once a day at DAILY_TIME (IST) while the Space is awake."""
    ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
    last = None
    while True:
        now = dt.datetime.now(ist)
        if now.strftime("%H:%M") == config.DAILY_TIME and last != now.date():
            last = now.date()
            try:
                pipeline.run_daily(30, THEME_NAMES[0], True)
            except Exception:
                traceback.print_exc()
        time.sleep(20)


if config.DAILY_TIME:
    threading.Thread(target=_scheduler, daemon=True).start()

if __name__ == "__main__":
    demo.queue().launch()
