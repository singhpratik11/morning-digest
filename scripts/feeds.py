# Feed sources for the digest, tuned for MBA-interview current affairs.
# Each feed: (bucket, source_name, url, max_items)
# The build script fetches these server-side (Indian feeds block browser/CORS access),
# tolerates failures, dedupes, and interleaves sources within a bucket.
# "Interview brief" and "Worth knowing" are curated lanes added by build_digest.py.

FEEDS = [
    # --- Economy & policy (India) ---
    ("Economy & policy", "Economic Times",   "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms", 4),
    ("Economy & policy", "Business Standard","https://www.business-standard.com/rss/economy-102.rss", 3),
    ("Economy & policy", "Mint",             "https://www.livemint.com/rss/economy", 3),
    ("Economy & policy", "The Hindu",        "https://www.thehindu.com/business/Economy/feeder/default.rss", 3),

    # --- Markets & banking ---
    ("Markets & banking", "Economic Times",   "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", 3),
    ("Markets & banking", "Business Standard","https://www.business-standard.com/rss/markets-106.rss", 3),
    ("Markets & banking", "Mint",             "https://www.livemint.com/rss/markets", 3),

    # --- Business & startups ---
    ("Business & startups", "Inc42",     "https://inc42.com/feed/", 3),
    ("Business & startups", "Entrackr",  "https://entrackr.com/rss", 3),

    # --- World ---
    ("World", "Al Jazeera",  "https://www.aljazeera.com/xml/rss/all.xml", 3),
    ("World", "BBC News",    "https://feeds.bbci.co.uk/news/world/rss.xml", 3),
    ("World", "The Guardian","https://www.theguardian.com/world/rss", 2),
]

# Section render order and how many items each keeps in the final edition.
# Current affairs lead; the curated interview brief sits mid-deck so it's hit early.
BUCKET_ORDER = [
    ("Economy & policy", 4),
    ("Markets & banking", 3),
    ("Interview brief", 1),     # curated: data/interview_briefs.json, one theme a day
    ("Business & startups", 3),
    ("World", 3),
    ("Worth knowing", 1),       # curated: scripts/deck_worth_knowing.json
]

# Curated lanes (not counted toward MIN_ITEMS).
CURATED = {"Interview brief", "Worth knowing"}

# If the run assembles fewer than this many news stories, keep the previous edition.
MIN_ITEMS = 8
