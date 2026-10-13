"""Fetch fresh AI items from free sources. Every source is wrapped so one failure never stops the run."""
import datetime as dt
import re
import xml.etree.ElementTree as ET
import requests
from config import UA, GITHUB_TOKEN, PAID_HINTS
import history


def _get(url, **kw):
    r = requests.get(url, headers=kw.pop("headers", UA), timeout=20, **kw)
    r.raise_for_status()
    return r


def hf_models(n=15):
    out = []
    for m in _get(f"https://huggingface.co/api/models?sort=trendingScore&limit={n}").json():
        mid = m.get("id") or m.get("modelId")
        out.append({"id": f"hfm:{mid}", "source": "HuggingFace model", "title": mid,
                    "url": f"https://huggingface.co/{mid}",
                    "text": f"{mid}. task: {m.get('pipeline_tag')}. likes: {m.get('likes')}. tags: {', '.join((m.get('tags') or [])[:8])}",
                    "kind": "model",
                    "meta": {"repo": mid, "likes": m.get("likes"), "badge": m.get("pipeline_tag") or "model", "site": "hf", "type": "Model"}})
    return out


def hf_spaces(n=15):
    out = []
    for s in _get(f"https://huggingface.co/api/spaces?sort=trendingScore&limit={n}").json():
        sid = s.get("id")
        out.append({"id": f"hfs:{sid}", "source": "HuggingFace Space (free demo)", "title": sid,
                    "url": f"https://huggingface.co/spaces/{sid}",
                    "text": f"{sid}. sdk: {s.get('sdk')}. likes: {s.get('likes')}. tags: {', '.join((s.get('tags') or [])[:8])}",
                    "kind": "tool",
                    "meta": {"repo": sid, "likes": s.get("likes"), "badge": s.get("sdk") or "space", "site": "hf", "type": "Space"}})
    return out


def github_new(n=15):
    since = (dt.date.today() - dt.timedelta(days=10)).isoformat()
    q = f"(topic:llm OR topic:ai OR topic:generative-ai OR topic:ai-agents) created:>{since}"
    headers = dict(UA)
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    data = _get("https://api.github.com/search/repositories", params={"q": q, "sort": "stars", "order": "desc", "per_page": n},
                headers=headers).json()
    out = []
    for r in data.get("items", []):
        lic = (r.get("license") or {}).get("spdx_id")
        out.append({"id": f"gh:{r['full_name']}", "source": "GitHub", "title": r["full_name"], "url": r["html_url"],
                    "text": f"{r['full_name']}: {r.get('description')}. stars: {r['stargazers_count']}. license: {lic}. lang: {r.get('language')}",
                    "kind": "pipeline",
                    "meta": {"repo": r["full_name"], "stars": r["stargazers_count"], "lang": r.get("language"),
                             "desc": r.get("description") or "", "license": lic if lic not in (None, "NOASSERTION") else "", "site": "gh"}})
    return out


def google_news(n=12):
    out = []
    for q in ["free open source AI tool", "new free AI tool launched", "open source AI workflow pipeline"]:
        xml = _get("https://news.google.com/rss/search", params={"q": q + " when:2d", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"}).text
        for it in ET.fromstring(xml).iter("item"):
            t = it.findtext("title") or ""
            out.append({"id": "gn:" + re.sub(r"\W+", "", t.lower())[:60], "source": "Google News", "title": t,
                        "url": it.findtext("link"), "text": t, "kind": "news"})
    return out[:n * 3]


def hacker_news(n=12):
    d = _get("https://hn.algolia.com/api/v1/search_by_date",
             params={"query": "open source AI", "tags": "story", "numericFilters": "points>30", "hitsPerPage": n}).json()
    return [{"id": f"hn:{h['objectID']}", "source": "Hacker News", "title": h.get("title", ""),
             "url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
             "text": f"{h.get('title')} ({h.get('points')} points)", "kind": "news"} for h in d.get("hits", [])]


def reddit_localllama(n=10):
    xml = _get("https://www.reddit.com/r/LocalLLaMA/top/.rss", params={"t": "day"}).text
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in ET.fromstring(xml).findall("a:entry", ns)[:n]:
        t = e.findtext("a:title", "", ns)
        link = e.find("a:link", ns).get("href")
        out.append({"id": "rd:" + re.sub(r"\W+", "", link)[-40:], "source": "Reddit r/LocalLLaMA", "title": t, "url": link,
                    "text": t, "kind": "news"})
    return out


SOURCES = [hf_spaces, hf_models, github_new, google_news, hacker_news, reddit_localllama]


def fetch_all(log=print):
    seen, items = history.used_ids(), []
    for fn in SOURCES:
        try:
            got = fn()
            log(f"✔ {fn.__name__}: {len(got)}")
            items += got
        except Exception as e:
            log(f"✘ {fn.__name__}: {type(e).__name__}: {str(e)[:80]}")
    uniq, ids = [], set()
    for it in items:
        low = it["text"].lower()
        if it["id"] in seen or it["id"] in ids or any(p in low for p in PAID_HINTS):
            continue
        ids.add(it["id"])
        uniq.append(it)
    return uniq
