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
   │    • pulls ~20 RSS feeds (India, world, business, tech, sport, offbeat)
   │    • rotates in one entry from the curated "Worth knowing" deck
   │    • writes data/digests.json  (stdlib only — no API key, no LLM)
   ▼
git commit + push  ──►  Vercel auto-deploys  ──►  the swipe app fetches digests.json
```

No API keys, no paid services, no daily approvals, no manual push. Everything runs on
GitHub Actions' free tier + Vercel's free tier.

## The content lanes
Each edition is a finite deck (~14 cards) for consulting, PM and operations job
interviews — news interleaved with practice, ending on a framework:
1. **Companies & industry** — ET, Business Standard, Mint
2. **Case brief** — an Indian company or industry case ([`data/case_briefs.json`](data/case_briefs.json)):
   role tag, the gist, three facts, a likely question, and a hidden "how to structure it"
3. **Startups & tech** — Inc42, Entrackr, ET Tech
4. **Guesstimate** — ([`data/guesstimates.json`](data/guesstimates.json)): question + hint up front,
   approach, ballpark and interviewer tip behind "try it first, then reveal"
5. **Economy & markets** · **Global business** — RSS
6. **Framework** — MECE, profitability tree, CIRCLES, RICE, Little's Law, Theory of Constraints…
   ([`data/frameworks.json`](data/frameworks.json))

Curated decks rotate one entry a day; add entries to lengthen the cycle. In curated
bodies, `¶` is a line break and `‖` splits what's shown from what the reveal hides.
Indian news feeds block browser (CORS) access, so they're fetched server-side by the
Action; the app just reads the latest `data/digests.json` whenever you open it.

## Morning news (cloud routine)
A Claude cloud routine runs daily at **07:00 IST**: it gathers the last 24 hours of news
with web search only (no page fetches, so no approval prompts), writes
`data/news_llm.json` — `{date, generatedAt, overview[2], sections[{name, items[{headline,
summary, source, url}]}]}` with sections Top stories / World / India / Business & markets /
Tech & AI / Sports — and pushes it. That push triggers the Action, which rebuilds the deck
with those sections first, the practice cards interleaved, and RSS as "Latest headlines".
If today's file is missing, the deck falls back to the RSS lanes.

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
