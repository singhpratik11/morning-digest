# Morning Digest

A calm, Inshorts-style **swipe reader** for a daily current-affairs digest. One story
per full screen, swipe up for the next, save the ones worth keeping — with a hard
"you're done" ending instead of an infinite feed.

- **Live app:** https://morning-digest-sigma.vercel.app (public, no login)
- **Source of the app:** [`index.html`](index.html) — a single, dependency-free HTML
  file (vanilla JS/CSS, Newsreader + Manrope, light/dark aware).

## How it works (self-sustaining, zero cost, zero manual steps)

```
GitHub Actions cron (a few times a day)
   │  scripts/build_digest.py
   │    • pulls ~25 RSS feeds (world, India, business, tech, sport, AI)
   │    • rotates in one case brief, guesstimate and framework
   │    • writes data/digests.json  (stdlib only — no API key, no LLM)
   ▼
git commit + push  ──►  Vercel auto-deploys  ──►  the swipe app fetches digests.json
```

No API keys, no paid services, no daily approvals, no manual push. Everything runs on
GitHub Actions' free tier + Vercel's free tier.

## The content lanes
Each edition is a finite deck (~45 cards) for consulting, PM and operations job interviews -
news interleaved with practice, ending on a framework:
1. **World** - BBC World, Al Jazeera, Guardian
2. **India** - The Hindu, Indian Express, NDTV, Hindustan Times
3. **Case brief** - an Indian company or industry case ([`data/case_briefs.json`](data/case_briefs.json))
4. **Business & markets** - ET, Business Standard, Mint, BBC Business
5. **Guesstimate** - ([`data/guesstimates.json`](data/guesstimates.json)), answer behind "try it first, then reveal"
6. **Startups & tech** - Inc42, Entrackr, ET Tech
7. **Sports** - ESPNcricinfo, BBC Sport, The Hindu
8. **Framework** - ([`data/frameworks.json`](data/frameworks.json))

Curated decks rotate one entry a day. In curated bodies, `¶` is a line break and `‖` splits
what's shown from what the reveal hides. Live blogs are skipped. Indian news feeds block
browser (CORS) access, so everything is fetched server-side by the Action.

## The app: three decks behind a bottom tab bar
**News · AI · IPOs · Saved.** Tap the active tab again to jump back to the first card; the top row
is just the edition date and a section picker.

## Story summaries (one small morning run)
Feeds mostly carry a one-sentence blurb, so the morning builds (04:00–08:59 IST) also save each
story's article text to `data/pool.json` (free; NDTV, ESPNcricinfo and Ars block it). A Claude
cloud routine, "Story summaries (7:15 AM IST)", with no web access, reads that file once and writes
`data/summaries.json`: 45–60 words per story (what happened, context, why it matters), using only
the article text. Every build uses those summaries instead of the blurbs; if the run fails or is
older than 36 hours, cards fall back to the blurbs.

## Look and feel
Apple-style: SF for text and New York for headlines on Apple devices (Manrope / Newsreader
elsewhere), a colour per section (World blue, India saffron, Business green, Startups purple,
Sports red, AI teal, IPOs green), frosted top bar and tab bar, and each story's own photo from its
feed (`item_image` in the build; ~85% of News cards). Content settles in as each card arrives;
switched off under Reduce Motion. The opening card is a "Today" cover with three photo stories.

## IPOs deck
Open and upcoming mainboard IPOs, one card each: status, industry, GMP (with the implied listing
gain, unofficial), issue size, fresh issue vs OFS (with the split), price band, lot size and the
cost of one lot, bidding and listing dates. Free: Chittorgarh's mainboard list and each IPO's page,
plus ipowatch's GMP table (`build_ipos` in `scripts/build_digest.py`); stored as `ipos` on the
day's edition. A scrape failure just hides the tab.

## AI deck
Also free RSS: TechCrunch AI, The Verge AI, Ars Technica AI, MIT Technology Review and
VentureBeat, routed by keyword into Labs & models / Chips & compute / China AI / Policy &
governments / Money & deals, plus India AI (ET Tech and Inc42 stories about AI). Stored as an
`ai` field on the day's edition.

## Cloud routines (paused)
Two Claude cloud routines used to write `data/news_llm.json` and `data/ai_llm.json` with web
search. They were paused on 6 Oct 2026: 2-8M tokens a run against the Pro plan, and the big
outlets now block the search crawler. The build still uses either file if one exists for today,
so they can be switched back on; otherwise everything is RSS and costs nothing.

## The pipeline
- [`scripts/feeds.py`](scripts/feeds.py) — the feed list, per-bucket caps, and `MIN_ITEMS`
  (below which a thin run keeps yesterday's edition instead of publishing).
- [`scripts/build_digest.py`](scripts/build_digest.py) — fetch, parse (RSS + Atom),
  clean, de-dupe, interleave sources, assemble the markdown, update `data/digests.json`.
- [`.github/workflows/digest.yml`](.github/workflows/digest.yml) — the cron + commit.
  Run it by hand anytime from the repo's **Actions** tab (workflow_dispatch).

Test locally: `python3 scripts/build_digest.py` (writes today's edition into `data/`).

### Data model
`data/digests.json` — an array of recent editions, newest first (cap 21):
`{ date, displayDate, markdown }`. The app parses `markdown` (title → date, two-line
tone, `## Section` buckets) into cards client-side. Saves are stored per-device in
`localStorage`.

## Adding to "Worth knowing"
Append objects to `scripts/deck_worth_knowing.json`:
`{ "title", "body", "source", "url" }`. The daily pick rotates through the whole deck,
so more entries = longer before anything repeats.

## Opening it on iPhone
Open the live URL in Safari → Share → **Add to Home Screen** for a full-screen app
icon. It shows the latest published edition and keeps on-device saves.

---
Built with Claude Code. Static site on Vercel; the only "backend" is a scheduled
GitHub Action. No server to run.
