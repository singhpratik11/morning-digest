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
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feeds import (FEEDS, BUCKET_ORDER, LLM_ORDER, AI_ORDER, AI_FEEDS, AI_RSS_ORDER,  # noqa: E402
                   MIN_ITEMS, CURATED, IPO_LIST_URL, IPO_GMP_URL, IPO_ORDER)

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


# --- IPOs: open + upcoming mainboard issues -------------------------------------------
MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
                                   "sep", "oct", "nov", "dec"], 1)}


def page_text(x):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", x)).split())


def table_fields(page):
    # First two cells of every table row -> {label: value}.
    out = {}
    for row in re.findall(r"<tr.*?</tr>", page, re.S):
        cells = [page_text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        if len(cells) >= 2 and cells[0] and cells[0] not in out:
            out[cells[0]] = cells[1]
    return out


def inr(n):
    # Indian digit grouping: 1465000 -> 14,65,000
    s = str(int(round(n)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
    return head + "," + tail


def ipo_key(name):
    k = re.sub(r"[^a-z0-9 ]", "", name.lower())
    k = re.sub(r"\b(ipo|limited|ltd|india|open|upcoming|closed)\b", "", k)
    return re.sub(r"\s+", "", k)


def ipo_dates(text, year_hint):
    # "15 to 19 Oct, 2026" / "29 Oct to 3 Nov, 2026" -> (date, date) or (None, None)
    m = re.search(r"(\d{1,2})\s*([A-Za-z]{3})?\w*\s+to\s+(\d{1,2})\s+([A-Za-z]{3})\w*,?\s*(\d{4})?", text or "")
    if not m:
        return None, None
    d1, m1, d2, m2, y = m.groups()
    m2n = MON.get(m2.lower()[:3])
    m1n = MON.get((m1 or m2).lower()[:3])
    y = int(y or year_hint)
    try:
        close = datetime(y, m2n, int(d2)).date()
        open_ = datetime(y - (1 if m1n > m2n else 0), m1n, int(d1)).date()
    except (TypeError, ValueError):
        return None, None
    return open_, close


def short_date(d):
    return "%d %s" % (d.day, MONTHS[d.month][:3])


def ipo_gmp():
    # ipowatch's first table is mainboard: Company | GMP | Trend | Price | Est. gain | Date
    raw = fetch(IPO_GMP_URL)
    if not raw:
        return {}
    page = raw.decode("utf-8", "ignore")
    tables = re.findall(r"<table.*?</table>", page, re.S)
    out = {}
    for row in re.findall(r"<tr.*?</tr>", tables[0] if tables else "", re.S):
        name = re.search(r"<a[^>]*>(.*?)</a>", row, re.S)
        cells = [page_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if not name or len(cells) < 2:
            continue
        g = re.search(r"(-?)\s*₹?\s*(-?\d[\d,]*)", cells[1])
        if g:
            val = int(g.group(2).replace(",", ""))
            out[ipo_key(page_text(name.group(1)))] = -abs(val) if g.group(1) else val
    return out


def ipo_card(url, name, status, today, gmps):
    raw = fetch(url)
    if not raw:
        return None
    page = re.sub(r"<script.*?</script>|<style.*?</style>", "", raw.decode("utf-8", "ignore"), flags=re.S)
    f = table_fields(page)
    open_, close = ipo_dates(f.get("IPO Date", ""), today.year)
    band = [int(x.replace(",", "")) for x in re.findall(r"₹\s*([\d,]+)", f.get("Price Band", ""))]
    top = band[-1] if band else None
    lot = re.search(r"([\d,]+)\s*Shares", f.get("Lot Size", ""))
    lot = int(lot.group(1).replace(",", "")) if lot else None

    def crore(label):
        m = re.search(r"₹\s*([\d,.]+)\s*Cr", f.get(label, ""))
        return "₹%s Cr" % m.group(1) if m else ""
    size, fresh, ofs = crore("Total Issue Size"), crore("Fresh Issue"), crore("Offer for Sale")
    sale = f.get("Sale Type", "")
    if fresh and ofs:
        kind = "fresh %s + OFS %s" % (fresh, ofs)
    elif re.search(r"(?i)ofs|offer for sale", sale) and not re.search(r"(?i)fresh", sale):
        kind = "OFS only"
    elif re.search(r"(?i)fresh", sale) and not re.search(r"(?i)offer for sale|ofs", sale):
        kind = "fresh issue only"
    else:
        kind = sale

    about = ""
    for m in re.finditer(r"<h[2-4][^>]*>(.*?)</h[2-4]>", page, re.S):
        if re.match(r"(?i)about\b", page_text(m.group(1))):
            para = re.search(r"<p[^>]*>(.*?)</p>", page[m.end():m.end() + 6000], re.S)
            if para:
                about = re.split(r"(?<=[a-z0-9)])\.\s", page_text(para.group(1)) + " ")[0]
            break
    cut = about.find(" is ")
    if 0 < cut < 90:                      # "X Ltd is one of India's ..." -> "One of India's ..."
        about = about[cut + 4:]
    about = clean_text(about[:1].upper() + about[1:], 120)

    if status == "open" and close:
        when = "Closes today" if close == today else "Open till " + short_date(close)
    elif open_:
        when = "Opens " + short_date(open_)
    else:
        when = "Dates to be announced"
    parts = ["**Status:** " + when]
    if about:
        parts.append("**Industry:** " + about)
    if size:
        parts.append("**Size:** " + size)
    if kind:
        parts.append("**Type:** " + kind)
    price = "₹%s–%s" % (inr(band[0]), inr(top)) if len(band) >= 2 else (f.get("Price Band") or "to be announced")
    lot_txt = ("%s shares (₹%s)" % (inr(lot), inr(lot * top))) if lot and top else "to be announced"
    parts.append("**Price band:** " + price)
    parts.append("**Lot:** " + lot_txt)
    gmp = next((v for k, v in gmps.items() if k and (k.startswith(ipo_key(name)[:8]) or
                                                     ipo_key(name).startswith(k[:8]))), None)
    if gmp is None:
        parts.append("**GMP:** not quoted yet")
    elif top:
        parts.append("**GMP:** ₹%d (%s%.0f%% est. listing, unofficial)" % (gmp, "+" if gmp >= 0 else "", 100.0 * gmp / top))
    else:
        parts.append("**GMP:** ₹%d (unofficial)" % gmp)
    lists = re.search(r"([A-Za-z]{3})\w*\s+(\d{1,2}),\s*(\d{4})", f.get("Listing Date", ""))
    if open_ and close:
        dates = ("%d–%s" % (open_.day, short_date(close)) if open_.month == close.month
                 else "%s–%s" % (short_date(open_), short_date(close)))
    else:
        dates = f.get("IPO Date", "")
    if dates:
        parts.append("**Dates:** " + dates)
    if lists and MON.get(lists.group(1).lower()):
        parts.append("**Listing:** %s %s" % (lists.group(2), MONTHS[MON[lists.group(1).lower()]][:3]))
    card = {"headline": brief_text(name), "body": " ¶".join(parts),
            "source": "Chittorgarh", "url": safe_url(url)}
    return (0 if status == "open" else 1, close or open_ or today, card)


def build_ipos(now):
    # {"Open now": [...closing soonest first], "Upcoming": [...]}; any failure -> {} (no IPO tab).
    try:
        raw = fetch(IPO_LIST_URL)
        page = raw.decode("utf-8", "ignore") if raw else ""
        listed, seen = [], set()
        for status, para in re.findall(r"(?is)<p>\s*The (current|upcoming) mainboard\b(.*?)</p>", page):
            for url, title in re.findall(r'href="(https://www\.chittorgarh\.com/ipo/[a-z0-9-]+/\d+/)"'
                                         r'\s+title="([^"]+)"', para):
                if url not in seen:
                    seen.add(url)
                    listed.append((url, re.sub(r"\s+IPO$", "", html.unescape(title)).strip(),
                                   "open" if status.lower() == "current" else "upcoming"))
        if not listed:
            log("  ! IPOs: no open or upcoming mainboard issues found")
            return {}
        gmps = ipo_gmp()
        cards = []
        for url, name, status in listed[:12]:
            time.sleep(1)
            c = ipo_card(url, name, status, now.date(), gmps)
            if c:
                cards.append(c)
        cards.sort(key=lambda c: (c[0], c[1]))
        log("IPOs:", len(cards), "| GMP quotes:", len(gmps))
        return {"Open now": [c[2] for c in cards if c[0] == 0],
                "Upcoming": [c[2] for c in cards if c[0] == 1]}
    except Exception as e:  # noqa: BLE001
        log("  ! IPOs failed:", type(e).__name__, e)
        return {}


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
    ipos = build_ipos(now)
    if any(ipos.values()):
        n_open, n_up = len(ipos["Open now"]), len(ipos["Upcoming"])
        mix = ("**%d open, %d upcoming.** GMP is the unofficial grey-market premium, a sentiment "
               "gauge, not a guarantee." % (n_open, n_up))
        md, _ = build_markdown(ipos, now, IPO_ORDER, None, mix)
        edition["ipos"] = md.replace(" picks**", " IPOs**", 1)
    editions.insert(0, edition)
    editions = editions[:MAX_EDITIONS]
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(editions, f, ensure_ascii=False, indent=1)
        f.write("\n")
    log("Wrote", DATA, "-", len(editions), "editions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
