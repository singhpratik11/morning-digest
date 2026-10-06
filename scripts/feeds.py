# Feed sources for the digest - free RSS, no LLM, no tokens. Lanes mirror a broad daily
# briefing (world, India, business, tech, sport) for consulting / PM / ops interview prep.
# Each feed: (bucket, source_name, url, max_items)
# Fetched server-side by the Action (Indian feeds block browser/CORS access); failures
# are skipped, items are de-duplicated and sources interleaved within a bucket.
# "Case brief", "Guesstimate" and "Framework" are curated lanes added by build_digest.py.

FEEDS = [
    # --- World ---
    ("World", "BBC World",  "https://feeds.bbci.co.uk/news/world/rss.xml", 4),
    ("World", "Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", 4),
    ("World", "Guardian",   "https://www.theguardian.com/world/rss", 3),

    # --- India ---
    ("India", "The Hindu",       "https://www.thehindu.com/news/national/feeder/default.rss", 3),
    ("India", "Indian Express",  "https://indianexpress.com/section/india/feed/", 3),
    ("India", "NDTV",            "https://feeds.feedburner.com/ndtvnews-india-news", 3),
    ("India", "Hindustan Times", "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml", 3),

    # --- Business & markets ---
    ("Business & markets", "Economic Times",   "https://economictimes.indiatimes.com/industry/rssfeeds/13352306.cms", 2),
    ("Business & markets", "Business Standard","https://www.business-standard.com/rss/companies-101.rss", 2),
    ("Business & markets", "Mint",             "https://www.livemint.com/rss/companies", 2),
    ("Business & markets", "Economic Times",   "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms", 2),
    ("Business & markets", "Mint",             "https://www.livemint.com/rss/markets", 2),
    ("Business & markets", "BBC Business",     "https://feeds.bbci.co.uk/news/business/rss.xml", 2),

    # --- Startups & tech ---
    ("Startups & tech", "Inc42",   "https://inc42.com/feed/", 3),
    ("Startups & tech", "Entrackr","https://entrackr.com/rss", 3),
    ("Startups & tech", "ET Tech", "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms", 3),

    # --- Sports ---
    ("Sports", "ESPNcricinfo", "https://www.espncricinfo.com/rss/content/story/feeds/0.xml", 3),
    ("Sports", "BBC Sport",    "https://feeds.bbci.co.uk/sport/rss.xml", 3),
    ("Sports", "The Hindu",    "https://www.thehindu.com/sport/feeder/default.rss", 2),
]

# Section render order and per-bucket caps. Curated cards are interleaved with the news
# so the deck alternates reading with practice, and it ends on a framework to keep.
BUCKET_ORDER = [
    ("World", 10),
    ("India", 10),
    ("Case brief", 1),          # curated: data/case_briefs.json
    ("Business & markets", 10),
    ("Guesstimate", 1),         # curated: data/guesstimates.json
    ("Startups & tech", 6),
    ("Sports", 6),
    ("Framework", 1),           # curated: data/frameworks.json
]

# The parallel AI deck, also free RSS. "AI" items are routed into sections by keyword
# (build_digest.ai_section); "India AI" feeds are general tech feeds kept only when the
# story is about AI.
AI_FEEDS = [
    ("AI", "TechCrunch",            "https://techcrunch.com/category/artificial-intelligence/feed/", 8),
    ("AI", "The Verge",             "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", 6),
    ("AI", "Ars Technica",          "https://arstechnica.com/ai/feed/", 6),
    ("AI", "MIT Technology Review", "https://www.technologyreview.com/topic/artificial-intelligence/feed", 5),
    ("AI", "VentureBeat",           "https://venturebeat.com/category/ai/feed/", 4),
    ("India AI", "ET Tech", "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms", 15),
    ("India AI", "Inc42",   "https://inc42.com/feed/", 15),
]

AI_RSS_ORDER = [
    ("Labs & models", 8),
    ("Chips & compute", 5),
    ("China AI", 4),
    ("Policy & governments", 5),
    ("Money & deals", 4),
    ("India AI", 4),
]

# Curated lanes (not counted toward MIN_ITEMS).
CURATED = {"Case brief", "Guesstimate", "Framework"}

# If the run assembles fewer than this many news stories, keep the previous edition.
MIN_ITEMS = 7

# Cloud-routine layout (routines PAUSED 6 Oct 2026 - too many tokens; kept so they can be
# switched back on). Used only when today's data/news_llm.json exists; otherwise BUCKET_ORDER.
LLM_ORDER = [
    ("Top stories", 5),
    ("World", 12),
    ("India", 12),
    ("Case brief", 1),
    ("Business & markets", 12),
    ("Guesstimate", 1),
    ("Tech & AI", 8),
    ("Science & health", 4),
    ("Sports", 7),
    ("Latest headlines", 8),    # RSS, refreshed through the day
    ("Framework", 1),
]

# AI-deck layout for a cloud-routine data/ai_llm.json (paused); otherwise AI_RSS_ORDER.
AI_ORDER = [
    ("AI top stories", 4),
    ("Chips & compute", 5),
    ("Labs & models", 5),
    ("China AI", 4),
    ("What the CEOs said", 4),
    ("Washington & policy", 4),
    ("World governments", 3),   # EU, UK, China, India, Japan, Korea, Gulf, G7/UN
    ("Money & deals", 3),
    ("India AI", 2),
]
