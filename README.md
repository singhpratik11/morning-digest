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
Each edition is a finite deck, ordered to hook then inform:
1. **Made me smile** — absurd-but-true offbeat news (grim items filtered out)
2. **India** · **World** · **Business & startups** · **Tech & science** · **Sports** — RSS
3. **Worth knowing** — a hand-written evergreen idea (mental model / finance concept /
   business case), rotated daily from [`scripts/deck_worth_knowing.json`](scripts/deck_worth_knowing.json)

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
