#!/usr/bin/env python3
"""Build one edition of the Morning Digest (news deck + AI deck) from RSS feeds + the curated decks,
and write it into data/digests.json. Zero third-party dependencies (stdlib only),
zero API keys, zero cost. Designed to run unattended from GitHub Actions.

It is tolerant: any feed that fails is skipped. If the run can't assemble at
least feeds.MIN_ITEMS stories, it leaves yesterday's edition untouched.
"""
import json
import os
import re
import sys
import html
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feeds import (FEEDS, BUCKET_ORDER, LLM_ORDER, AI_ORDER, AI_FEEDS, AI_RSS_ORDER,  # noqa: E402
                   MIN_ITEMS, CURATED)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "digests.json")
DECK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck_worth_knowing.json")
CASES = os.path.join(ROOT, "data", "case_briefs.json")
GUESSES = os.path.join(ROOT, "data", "guesstimates.json")
FRAMES = os.path.join(ROOT, "data", "frameworks.json")
NEWS_LLM = os.path.join(ROOT, "data", "news_llm.json")   # written by the 07:00 IST cloud routine
AI_LLM = os.path.join(ROOT, "data", "ai_llm.json")       # written by the 07:30 IST AI routine
MAX_EDITIONS = 21
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
IST = timezone(timedelta(hours=5, minutes=30))
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def fetch(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        log("  ! fetch failed:", url, type(e).__name__, e)
        return None


def strip_ns(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
# "6.5-7%" is a range, not a fall: en-dash it so the app's red/green % colouring skips it.
RANGE_RE = re.compile(r"(\d)-(\d)")

# "Made me smile" should be light. Drop offbeat-feed items that are actually grim.
BLOCK_SMILE = re.compile(r"\b(dead|dies|died|death|kill|killed|murder|shoot|shot|"
                         r"stab|stabbed|rape|raped|assault|abuse|kidnap|kidnapped|"
                         r"terror|bomb|blast|crash|quake|flood|wildfire|war|attack|"
                         r"suicide|missing|tragedy|hostage|victim|injured|wounded|"
                         r"drown|drowned|beheaded|dismember|corpse|overdose|"
                         r"paedophile|pedophile|molest|manslaughter)\b", re.I)


# Live blogs ("India News Live Updates, 6 October") are rolling pages, not stories.
LIVE_RE = re.compile(r"\blive(?: updates?| blog|:)", re.I)


def clean_text(s, limit=320):
    if not s:
        return ""
    s = TAG_RE.sub(" ", s)
    s = html.unescape(s)
    s = s.replace("[", "").replace("]", "")   # keep the app's link parser safe
    s = s.replace("*", "")
    s = RANGE_RE.sub("\\1\u2013\\2", WS_RE.sub(" ", s).strip())
    # drop common RSS boilerplate tails
    s = re.split(r"(?i)\b(the post|read more|continue reading|appeared first on)\b", s)[0].strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    dot = cut.rfind(". ")
    if dot > limit * 0.5:
        return cut[:dot + 1]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > 0 else cut).rstrip(",;: ") + "…"


def elem_text(el):
    return (el.text or "").strip() if el is not None else ""


def get_link(item):
    # RSS: <link>text</link>. Atom: <link href="..." rel="alternate"/>
    best = ""
    for ln in item:
        if strip_ns(ln.tag) != "link":
            continue
        href = ln.attrib.get("href")
        if href:
            rel = ln.attrib.get("rel", "alternate")
            if rel == "alternate":
                return href.strip()
            best = best or href.strip()
        elif (ln.text or "").strip():
            return ln.text.strip()
    return best


def parse_feed(raw):
    """Return a list of (title, link, description) from RSS or Atom bytes."""
    if not raw:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        try:
            root = ET.fromstring(raw.decode("utf-8", "ignore"))
        except Exception:  # noqa: BLE001
            return []
    out = []
    for node in root.iter():
        if strip_ns(node.tag) not in ("item", "entry"):
            continue
        title = link = desc = ""
        for ch in node:
            t = strip_ns(ch.tag)
            if t == "title" and not title:
                title = elem_text(ch)
            elif t in ("description", "summary") and not desc:
                desc = elem_text(ch)
            elif t == "content" and not desc:
                desc = elem_text(ch)
        link = get_link(node)
        title = html.unescape(TAG_RE.sub("", title)).strip()
        if title and link:
            out.append((title, link.strip(), desc))
    return out


def norm(title):
    return re.sub(r"[^a-z0-9]+", "", title.lower())[:60]


def safe_url(u):
    u = (u or "").strip()
    if not re.match(r"^https?://", u):
        return ""
    return u.replace(")", "%29").replace("(", "%28").replace(" ", "%20")


def collect(feeds=FEEDS):
    # Fetch each feed into its own list, then round-robin merge within a bucket so
    # sources are interleaved (not five stories from whichever feed came first).
    per_bucket = []       # list of (bucket, [feed_list, feed_list, ...]) preserving order
    index = {}
    for bucket, source, url, maxn in feeds:
        log("- fetching", source, "->", bucket)
        items = parse_feed(fetch(url))
        feed_list, taken = [], 0
        for title, link, desc in items:
            if taken >= maxn:
                break
            u = safe_url(link)
            if not u or not norm(title) or LIVE_RE.search(title):
                continue
            if bucket == "Made me smile" and BLOCK_SMILE.search(title):
                continue
            body = "" if source == "Not the Onion" else \
                clean_text(desc, 220 if bucket == "Made me smile" else 320)
            feed_list.append({"headline": clean_text(title, 160), "body": body,
                              "source": source, "url": u, "key": norm(title)})
            taken += 1
        log("    kept", taken)
        if bucket not in index:
            index[bucket] = len(per_bucket)
            per_bucket.append((bucket, []))
        per_bucket[index[bucket]][1].append(feed_list)

    buckets, seen = {}, set()
    for bucket, feed_lists in per_bucket:
        merged, i = [], 0
        while any(i < len(fl) for fl in feed_lists):
            for fl in feed_lists:
                if i < len(fl):
                    it = fl[i]
                    if it["key"] not in seen:
                        seen.add(it["key"])
                        merged.append(it)
            i += 1
        buckets[bucket] = merged
    return buckets


def add_worth_knowing(buckets, doy):
    try:
        deck = json.load(open(DECK, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log("  ! curated deck unavailable:", e)
        return
    if not deck:
        return
    n = len(deck)
    idxs = [doy % n, (doy * 7 + 3) % n]
    picks, used = [], set()
    for i in idxs:
        if i in used:
            i = (i + 1) % n
        used.add(i)
        picks.append(deck[i])
    buckets["Worth knowing"] = [
        {"headline": clean_text(p["title"], 160), "body": clean_text(p["body"], 340),
         "source": p.get("source", ""), "url": safe_url(p.get("url", ""))}
        for p in picks]


def brief_text(s):
    # Like clean_text but keeps the **bold** labels and the ¶ line-break marker the app renders.
    s = html.unescape(str(s or "")).replace("[", "").replace("]", "").replace("*", "")
    return RANGE_RE.sub("\\1\u2013\\2", WS_RE.sub(" ", s).strip())


def pick(path, doy, label):
    # One entry a day from a curated deck, rotating by day of year.
    try:
        deck = json.load(open(path, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log("  ! %s unavailable:" % label, e)
        return None
    return deck[doy % len(deck)] if deck else None


def curated_card(headline, body, source, url):
    return {"headline": brief_text(headline), "body": body,
            "source": source or "Reference", "url": safe_url(url)}


def add_curated(buckets, doy):
    # Body labels are bold; "¶" is a line break and "‖" splits what's shown from what's
    # behind the app's "try it first, then reveal" control.
    b = pick(CASES, doy, "case briefs")
    if b:
        facts = " ".join("(%d) %s" % (i + 1, brief_text(f)) for i, f in enumerate(b.get("facts", [])[:3]))
        body = ("**For:** %s ¶**The gist:** %s ¶**Know these:** %s ¶**Likely question:** %s "
                "‖**How to structure it:** %s"
                % (brief_text(b["roles"]), brief_text(b["gist"]), facts,
                   brief_text(b["question"]), brief_text(b["structure"])))
        buckets["Case brief"] = [curated_card(b["topic"], body, b.get("source"), b.get("url"))]

    g = pick(GUESSES, doy, "guesstimates")
    if g:
        body = ("**For:** Consulting · PM ¶**Hint:** %s ‖**Approach:** %s ¶**Ballpark:** %s "
                "¶**Interviewer tip:** %s"
                % (brief_text(g["hint"]), brief_text(g["approach"]),
                   brief_text(g["ballpark"]), brief_text(g["tip"])))
        buckets["Guesstimate"] = [curated_card(g["prompt"], body, "Practice", "")]

    f = pick(FRAMES, doy, "frameworks")
    if f:
        body = ("**For:** %s ¶**What it is:** %s ¶**Use it when:** %s ¶**Example:** %s"
                % (brief_text(f["roles"]), brief_text(f["what"]),
                   brief_text(f["when"]), brief_text(f["example"])))
        buckets["Framework"] = [curated_card(f["name"], body, f.get("source"), f.get("url"))]


def load_llm(path, order, date):
    # Today's synthesized deck from a cloud routine, or None (missing, stale or malformed).
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if d.get("date") != date:
        log("  %s is for %s, not today - skipping it." % (os.path.basename(path), d.get("date")))
        return None
    names = {b for b, _ in order}
    buckets = {}
    for sec in d.get("sections", []):
        name = sec.get("name", "")
        if name not in names:
            continue
        items = []
        for it in sec.get("items", []):
            h, u = brief_text(it.get("headline")), safe_url(it.get("url"))
            if h:
                items.append({"headline": h[:160], "body": brief_text(it.get("summary")),
                              "source": brief_text(it.get("source")), "url": u})
        buckets[name] = items
    if not buckets:
        return None
    # Re-bold a leading "Label:" (brief_text strips asterisks), e.g. "**Markets:** ...".
    # Capped so a long line can't overflow the intro card (clean_text cuts at a sentence/word).
    overview = [re.sub(r"^([A-Z][A-Za-z &-]{1,24}):\s*", r"**\1:** ", clean_text(x, 150))
                for x in d.get("overview", [])][:2]
    return buckets, overview


# AI deck from RSS: route each story into a section by keyword (first match wins).
AI_WORD = re.compile(r"\b(ai|a\.i\.|artificial intelligence|genai|gen ai|llms?|gpt|chatgpt|openai|"
                     r"gemini|agentic|machine learning|deep learning)\b", re.I)
INDIA_WORD = re.compile(r"\b(india|indian|bengaluru|bangalore|mumbai|delhi|hyderabad|chennai|pune|"
                        r"meity|indiaai|reliance|jio|tcs|infosys|wipro|hcl|sarvam|krutrim)\b", re.I)
AI_ROUTES = [
    ("Policy & governments", re.compile(
        r"\b(trump|white house|congress|senate|regulat\w*|lawsuits?|sued|court|judge|bans?|banned|"
        r"export controls?|tariffs?|government|ministry|eu|european|commission|ai act|policy|"
        r"laws?|ftc|doj|antitrust|parliament|watermark\w*)\b", re.I)),
    ("China AI", re.compile(
        r"\b(china|chinese|beijing|deepseek|kimi|moonshot|alibaba|qwen|baidu|bytedance|tencent|"
        r"huawei|zhipu|minimax)\b", re.I)),
    ("Chips & compute", re.compile(
        r"\b(nvidia|amd|tsmc|intel|broadcom|arm|qualcomm|chips?|semiconductors?|gpus?|tpus?|"
        r"data ?cent(er|re)s?|compute|coreweave|stargate|oracle|supercomputer)\b", re.I)),
    ("Money & deals", re.compile(
        r"\b(funding|raises|raised|valuation|valued|ipo|acquires?|acquired|acquisition|"
        r"invest(s|ment|ors?)?|series [a-f]|deal)\b", re.I)),
]


def ai_section(it):
    text = it["headline"] + " " + it["body"]
    for name, rx in AI_ROUTES:
        if rx.search(text):
            return name
    return "Labs & models"


def build_ai_rss():
    pool = collect(AI_FEEDS)
    out = {name: [] for name, _ in AI_RSS_ORDER}
    for it in pool.get("India AI", []):
        text = it["headline"] + " " + it["body"]
        # ET Tech also carries global wire copy, so it needs an India angle; Inc42 is all-India.
        if AI_WORD.search(text) and (it["source"] == "Inc42" or INDIA_WORD.search(text)):
            out["India AI"].append(it)
    for it in pool.get("AI", []):
        out[ai_section(it)].append(it)
    return out


def latest_headlines(rss):
    # Interleave the RSS lanes into one short, intra-day "Latest headlines" section.
    lanes = [rss.get(b, []) for b, _ in BUCKET_ORDER if b not in CURATED]
    out, i = [], 0
    while any(i < len(l) for l in lanes):
        out.extend(l[i] for l in lanes if i < len(l))
        i += 1
    return out


NEWS_MIX = ("**The mix:** world, India, business, tech and sport, plus a case to crack, "
            "a guesstimate to try and a framework to keep.")
AI_MIX = "**The mix:** chips, labs, China, what the CEOs said and what Washington is doing."
AI_RSS_MIX = "**The mix:** labs, chips, China, policy, money and India AI, straight from the outlets."


def build_markdown(buckets, now, order, overview=None, mix=NEWS_MIX):
    display = "%s, %d %s %d" % (WEEKDAYS[now.weekday()], now.day, MONTHS[now.month], now.year)
    total = 0
    for b, cap in order:
        total += min(len(buckets.get(b, [])), cap)
    lines = ["# " + display, ""]
    lines.append("**%d picks**, fresh as of %02d:%02d IST." % (total, now.hour, now.minute))
    if overview:
        lines.extend(overview[:2])
    else:
        lines.append(mix)
    lines.append("")
    for bucket, cap in order:
        items = buckets.get(bucket, [])[:cap]
        if not items:
            continue
        lines.append("## " + bucket)
        lines.append("")
        for it in items:
            link = " [%s](%s)" % (it["source"], it["url"]) if it["url"] and it["source"] else ""
            body = (" " + it["body"]) if it["body"] else ""
            lines.append("**%s**%s%s" % (it["headline"], body, link))
            lines.append("")
    return "\n".join(lines).strip() + "\n", total


def main():
    now = datetime.now(IST)
    date = now.strftime("%Y-%m-%d")
    doy = int(now.strftime("%j"))
    log("Building edition for", date)

    rss = collect()
    llm = load_llm(NEWS_LLM, LLM_ORDER, date)
    if llm:
        buckets, overview = llm
        buckets["Latest headlines"] = latest_headlines(rss)
        order = LLM_ORDER
        log("Using today's cloud-routine news (%d sections)." % len(buckets))
    else:
        buckets, overview, order = rss, None, BUCKET_ORDER
    add_curated(buckets, doy)
    markdown, total = build_markdown(buckets, now, order, overview)

    story_count = sum(min(len(buckets.get(b, [])), cap)
                      for b, cap in order if b not in CURATED)
    log("News stories (excl. curated):", story_count, "| total:", total)
    if story_count < MIN_ITEMS:
        log("Too few stories (%d < %d) - keeping yesterday's edition." % (story_count, MIN_ITEMS))
        return 0

    try:
        editions = json.load(open(DATA, encoding="utf-8"))
        if not isinstance(editions, list):
            editions = []
    except Exception:  # noqa: BLE001
        editions = []
    editions = [e for e in editions if e.get("date") != date]
    edition = {"date": date, "displayDate":
               "%s, %d %s %d" % (WEEKDAYS[now.weekday()], now.day, MONTHS[now.month], now.year),
               "markdown": markdown}
    ai = load_llm(AI_LLM, AI_ORDER, date)
    if ai:
        edition["ai"], ai_total = build_markdown(ai[0], now, AI_ORDER, ai[1], AI_MIX)
    else:
        edition["ai"], ai_total = build_markdown(build_ai_rss(), now, AI_RSS_ORDER, None, AI_RSS_MIX)
    if ai_total < MIN_ITEMS:
        del edition["ai"]   # too thin to show; the app hides the AI switch
    log("AI deck:", ai_total, "stories.")
    editions.insert(0, edition)
    editions = editions[:MAX_EDITIONS]
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(editions, f, ensure_ascii=False, indent=1)
        f.write("\n")
    log("Wrote", DATA, "-", len(editions), "editions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
