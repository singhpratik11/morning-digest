#!/usr/bin/env python3
"""Build one edition of the Morning Digest from RSS feeds + the curated deck,
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
from feeds import FEEDS, BUCKET_ORDER, MIN_ITEMS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "digests.json")
DECK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck_worth_knowing.json")
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

# "Made me smile" should be light. Drop offbeat-feed items that are actually grim.
BLOCK_SMILE = re.compile(r"\b(dead|dies|died|death|kill|killed|murder|shoot|shot|"
                         r"stab|stabbed|rape|raped|assault|abuse|kidnap|kidnapped|"
                         r"terror|bomb|blast|crash|quake|flood|wildfire|war|attack|"
                         r"suicide|missing|tragedy|hostage|victim|injured|wounded|"
                         r"drown|drowned|beheaded|dismember|corpse|overdose|"
                         r"paedophile|pedophile|molest|manslaughter)\b", re.I)


def clean_text(s, limit=320):
    if not s:
        return ""
    s = TAG_RE.sub(" ", s)
    s = html.unescape(s)
    s = s.replace("[", "").replace("]", "")   # keep the app's link parser safe
    s = s.replace("*", "")
    s = WS_RE.sub(" ", s).strip()
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


def collect():
    # Fetch each feed into its own list, then round-robin merge within a bucket so
    # sources are interleaved (not five stories from whichever feed came first).
    per_bucket = []       # list of (bucket, [feed_list, feed_list, ...]) preserving order
    index = {}
    for bucket, source, url, maxn in FEEDS:
        log("- fetching", source, "->", bucket)
        items = parse_feed(fetch(url))
        feed_list, taken = [], 0
        for title, link, desc in items:
            if taken >= maxn:
                break
            u = safe_url(link)
            if not u or not norm(title):
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


def build_markdown(buckets, now):
    display = "%s, %d %s %d" % (WEEKDAYS[now.weekday()], now.day, MONTHS[now.month], now.year)
    total = 0
    for b, cap in BUCKET_ORDER:
        total += min(len(buckets.get(b, [])), cap)
    lines = ["# " + display, ""]
    lines.append("**%d picks**, fresh as of %02d:%02d IST." % (total, now.hour, now.minute))
    lines.append("**The mix:** what moved today, an idea worth knowing, and something too absurd to be made up.")
    lines.append("")
    for bucket, cap in BUCKET_ORDER:
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

    buckets = collect()
    add_worth_knowing(buckets, doy)
    markdown, total = build_markdown(buckets, now)

    story_count = sum(min(len(buckets.get(b, [])), cap)
                      for b, cap in BUCKET_ORDER if b != "Worth knowing")
    log("Story cards (excl. Worth knowing):", story_count, "| total:", total)
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
    editions.insert(0, {"date": date, "displayDate":
                        "%s, %d %s %d" % (WEEKDAYS[now.weekday()], now.day, MONTHS[now.month], now.year),
                        "markdown": markdown})
    editions = editions[:MAX_EDITIONS]
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(editions, f, ensure_ascii=False, indent=1)
        f.write("\n")
    log("Wrote", DATA, "-", len(editions), "editions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
