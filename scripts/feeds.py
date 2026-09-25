# Feed sources for the digest, tuned for consulting / PM / operations job interviews:
# company and industry news first, then startups and tech, then a lighter macro lane.
# Each feed: (bucket, source_name, url, max_items)
# Fetched server-side by the Action (Indian feeds block browser/CORS access); failures
# are skipped, items are de-duplicated and sources interleaved within a bucket.
# "Case brief", "Guesstimate" and "Framework" are curated lanes added by build_digest.py.

FEEDS = [
    # --- Companies & industry ---
    ("Companies & industry", "Economic Times",   "https://economictimes.indiatimes.com/industry/rssfeeds/13352306.cms", 3),
    ("Companies & industry", "Business Standard","https://www.business-standard.com/rss/companies-101.rss", 3),
    ("Companies & industry", "Mint",             "https://www.livemint.com/rss/companies", 3),

    # --- Startups & tech ---
    ("Startups & tech", "Inc42",   "https://inc42.com/feed/", 3),
    ("Startups & tech", "Entrackr","https://entrackr.com/rss", 3),
    ("Startups & tech", "ET Tech", "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms", 3),

    # --- Economy & markets ---
    ("Economy & markets", "Economic Times",   "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms", 2),
    ("Economy & markets", "Business Standard","https://www.business-standard.com/rss/economy-102.rss", 2),
    ("Economy & markets", "Mint",             "https://www.livemint.com/rss/markets", 2),

    # --- Global business ---
    ("Global business", "BBC Business",     "https://feeds.bbci.co.uk/news/business/rss.xml", 2),
    ("Global business", "Guardian Business","https://www.theguardian.com/uk/business/rss", 2),
]

# Section render order and per-bucket caps. Curated cards are interleaved with the news
# so the deck alternates reading with practice, and it ends on a framework to keep.
BUCKET_ORDER = [
    ("Companies & industry", 3),
    ("Case brief", 1),          # curated: data/case_briefs.json
    ("Startups & tech", 3),
    ("Guesstimate", 1),         # curated: data/guesstimates.json
    ("Economy & markets", 3),
    ("Global business", 2),
    ("Framework", 1),           # curated: data/frameworks.json
]

# Curated lanes (not counted toward MIN_ITEMS).
CURATED = {"Case brief", "Guesstimate", "Framework"}

# If the run assembles fewer than this many news stories, keep the previous edition.
MIN_ITEMS = 7

# When the 7 AM cloud routine has written today's data/news_llm.json, the deck uses these
# sections instead: synthesized news first, practice interleaved, RSS as "Latest headlines"
# for intra-day freshness. If today's file is missing, BUCKET_ORDER (RSS only) is used.
LLM_ORDER = [
    ("Top stories", 3),
    ("World", 5),
    ("India", 5),
    ("Case brief", 1),
    ("Business & markets", 5),
    ("Guesstimate", 1),
    ("Tech & AI", 4),
    ("Sports", 3),
    ("Latest headlines", 4),    # RSS, refreshed through the day
    ("Framework", 1),
]
