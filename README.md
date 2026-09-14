# Morning Digest

A calm, Inshorts-style **swipe app** for Pratik's daily news brief. One story per
full screen, swipe up for the next, save the ones worth keeping.

- **Live app:** https://claude.ai/code/artifact/3c3963a0-f493-43f7-a196-b6e381c2e293
  (private Claude Artifact — opens when signed into claude.ai)
- **Source of the app:** [`morning-digest.html`](morning-digest.html) — a single,
  dependency-free HTML file (vanilla JS/CSS, Newsreader + Manrope, light/dark aware).

## How the whole chain works (fully automated)

```
9:00 AM IST  ─►  Cloud routine "Daily news digest (9 AM IST)"
                 (Anthropic cloud, model opus-5, cron 30 3 * * *)
                    │  fetches the fixed source list, composes the digest,
                    │  delivers it as a chat message + phone push (as before)
                    ▼
                 writes the FULL digest markdown into the app's database
                 (Artifact tool → write_db, collection "digests", doc = date)
                    ▼
             Morning Digest app reads it live and renders the swipe feed
```

Nothing is manual. Each morning a new dated edition appears in the app on its own.

### Data model (Artifact `db`)
- `digests/{YYYY-MM-DD}` → `{ date, displayDate, markdown, createdAt }`
  The app parses `markdown` (title → date, two-line tone, `## Top 3 today`,
  five buckets, `## Worth opening yourself`) into cards client-side.
- `saved/{itemId}` → the articles the reader bookmarked (synced across devices
  inside the Claude viewer; mirrored to `localStorage` on each device).

### The cloud routine
- Trigger id: `trig_01RU3N46sjxuDjVVYF92KJej`
- Managed from Claude Code via the `schedule` skill / `RemoteTrigger` tool.
- The prompt is in [`docs/routine-prompt.txt`](docs/routine-prompt.txt); its final
  "SAVE TO PRATIK'S READING APP" section is what writes into the app. Everything
  else (schedule, model, system prompt, MCP config) is the original tuned routine.
- A sample edition it produces: [`docs/sample-digest-2026-09-14.json`](docs/sample-digest-2026-09-14.json).

## Updating the app
Edit `morning-digest.html`, then in Claude Code republish it to the **same** artifact
URL (the Artifact tool, same file path / same URL) so the link and database persist.
The page also carries a baked-in `EMBEDDED` copy of the latest edition as an offline
fallback for the home-screen/PWA view.

## Opening it on iPhone
- **Claude iOS app** (signed in): full live experience — daily auto-updates + saved
  articles that sync across devices.
- **Add to Home Screen** (Safari → Share → Add to Home Screen): an app icon that opens
  full-screen; shows the last synced/baked edition and keeps on-device saves offline.

---
Built with Claude Code. The app runs as a Claude Artifact; there is no server to host.
