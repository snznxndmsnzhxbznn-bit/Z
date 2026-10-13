import config
import history
import render
import scriptgen
import sources
import tg
import voice

DEFAULT_THEME = list(config.THEMES.keys())[0]


def attach_meta(beats, item):
    for b in beats:
        b["meta"] = item.get("meta") or {}
    return beats


def make_video(beats, target=30, theme=DEFAULT_THEME, log=print, progress=None):
    """Voice first (its length decides each scene's length), then render + mux in one go."""
    track = voice.synthesize(beats, float(target), log)
    return render.render(beats, track, theme=theme, progress=progress)


def run_daily(duration=30, theme=DEFAULT_THEME, send=False, log=print, progress=None):
    items = sources.fetch_all(log)
    log(f"कुल नए कैंडिडेट: {len(items)}")
    item, script = scriptgen.make_script(items, config.CHANNEL_NAME, log)
    log(f"चुना: {item['title']}  ({item['source']})")
    beats = attach_meta(scriptgen.beats_from(script, item), item)
    video = make_video(beats, duration, theme, log, progress)
    history.mark(item["id"], item["title"])
    log("🎬 वीडियो तैयार (वॉइस के साथ)")
    if send:
        log(tg.send(video, script.get("caption", "") + "\n\n" + " ".join(script.get("hashtags", [])), script.get("guide", "")))
    return item, script, beats, video
