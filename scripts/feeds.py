# Feed sources for the Morning Digest, grouped into the app's sections.
# Each feed: (bucket, source_name, url, max_items)
# The build script fetches these, tolerates failures, dedupes, and caps per bucket.
# Buckets render in the order first seen below. "Made me smile" leads (the hook),
# then the news lanes, then "Worth knowing" (curated, added by the build script).

FEEDS = [
    # --- Made me smile: absurd-but-true, funny-because-real ---
    # (lighter sources first; a tragedy/violence filter in build_digest.py drops grim items)
    ("Made me smile", "Not the Onion", "https://www.reddit.com/r/nottheonion/top/.rss?t=day", 5),
    ("Made me smile", "UPI Odd News",  "https://rss.upi.com/news/odd_news.rss", 5),
    ("Made me smile", "Metro Weird",   "https://metro.co.uk/news/weird/feed/", 5),

    # --- India: markets, economy, national, corporate ---
    ("India", "Economic Times",   "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", 4),
    ("India", "Economic Times",   "https://economictimes.indiatimes.com/rssfeedstopstories.cms", 4),
    ("India", "Business Standard","https://www.business-standard.com/rss/markets-106.rss", 3),
    ("India", "The Hindu",        "https://www.thehindu.com/news/national/feeder/default.rss", 3),
    ("India", "NDTV",             "https://feeds.feedburner.com/ndtvnews-top-stories", 3),
    ("India", "Times of India",   "https://timesofindia.indiatimes.com/rssfeedstopstories.cms", 3),

    # --- World ---
    ("World", "Al Jazeera",  "https://www.aljazeera.com/xml/rss/all.xml", 4),
    ("World", "BBC News",    "https://feeds.bbci.co.uk/news/world/rss.xml", 4),
    ("World", "The Guardian","https://www.theguardian.com/world/rss", 3),

    # --- Business & startups ---
    ("Business & startups", "Inc42",      "https://inc42.com/feed/", 3),
    ("Business & startups", "Entrackr",   "https://entrackr.com/rss", 3),
    ("Business & startups", "YourStory",  "https://yourstory.com/feed", 2),
    ("Business & startups", "TechCrunch", "https://techcrunch.com/feed/", 3),

    # --- Tech & science ---
    ("Tech & science", "Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", 3),
    ("Tech & science", "The Verge",    "https://www.theverge.com/rss/index.xml", 3),
    ("Tech & science", "ScienceDaily", "https://www.sciencedaily.com/rss/top/science.xml", 3),
    ("Tech & science", "Phys.org",     "https://phys.org/rss-feed/", 2),

    # --- Sports (cricket first) ---
    ("Sports", "ESPNcricinfo", "https://www.espncricinfo.com/rss/content/story/feeds/0.xml", 3),
    ("Sports", "BBC Sport",    "https://feeds.bbci.co.uk/sport/rss.xml", 3),
]

# Section render order and how many items each keeps in the final edition.
BUCKET_ORDER = [
    ("Made me smile", 3),
    ("India", 5),
    ("World", 4),
    ("Business & startups", 4),
    ("Tech & science", 4),
    ("Sports", 3),
    ("Worth knowing", 2),   # filled from the curated deck, not RSS
]

# If the whole run assembles fewer than this many story cards, skip writing
# (keep yesterday's edition rather than publish a thin/broken one).
MIN_ITEMS = 8
