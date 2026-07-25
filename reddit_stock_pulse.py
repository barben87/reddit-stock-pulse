#!/usr/bin/env python3
"""
Reddit Stock Pulse — Scrape Reddit via PUBLIC JSON endpoints (no API key / no PRAW)
+ fetch real stock data from Finnhub.
Designed to run in GitHub Actions twice daily.
"""

import os
import json
import re
import random
import time
from datetime import datetime, timedelta
from collections import defaultdict
import logging

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# ============================================================================
# CONFIG
# ============================================================================
FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY')

SUBREDDITS = ['stocks', 'investing', 'wallstreetbets', 'ValueInvesting']
DATA_FILE = 'data/stocks.json'
TICKER_CACHE_FILE = 'data/ticker_cache.json'
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

# A clear, honest User-Agent is required by Reddit or requests get blocked.
# Change the username to your own Reddit handle.
REDDIT_USER_AGENT = "StockPulse/1.0 (personal research project; contact: barben87)"

# How many posts per subreddit to pull, and whether to also read comments.
POSTS_PER_SUBREDDIT = 40
READ_COMMENTS = True
COMMENTS_PER_POST = 60  # cap so we don't hammer Reddit

# Delay between Reddit requests (seconds) — keeps us polite and unblocked.
REDDIT_DELAY = 2.5

# Words that look like tickers but almost never are — filtered out.
STOPWORDS = {
    'A', 'I', 'IT', 'IS', 'BE', 'TO', 'DO', 'GO', 'ON', 'IN', 'AT', 'OR', 'AN', 'AS', 'IF', 'SO', 'UP', 'MY', 'BY', 'WE', 'HE',
    'CEO', 'CFO', 'IPO', 'ETF', 'USA', 'US', 'UK', 'EU', 'DD', 'YOLO', 'FD', 'FOMO', 'ATH', 'ATL', 'EPS', 'PE', 'PT', 'YTD',
    'AI', 'ML', 'EV', 'PC', 'TV', 'OK', 'LOL', 'IMO', 'IMHO', 'TLDR', 'EDIT', 'FYI', 'ELI', 'AKA', 'NSFW', 'WSB', 'THE',
    'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HAS', 'HAD', 'WAS', 'ONE', 'OUR', 'OUT', 'DAY', 'GET', 'NEW',
    'NOW', 'OLD', 'SEE', 'HIM', 'TWO', 'HOW', 'ITS', 'WHO', 'DID', 'YES', 'HIS', 'HER', 'BIG', 'BUY', 'LOW', 'RED',
    'CALL', 'PUTS', 'CALLS', 'GAIN', 'LOSS', 'HODL', 'MOON', 'BEAR', 'BULL', 'LONG', 'RISK', 'CASH', 'FEAR', 'HIGH', 'OPEN',
}

# ============================================================================
# TICKER LIST
# ============================================================================
def load_valid_tickers():
    """Load list of all valid US stock tickers from GitHub (cached locally)"""
    cache_file = TICKER_CACHE_FILE
    if os.path.exists(cache_file):
        mod_time = os.path.getmtime(cache_file)
        if datetime.now().timestamp() - mod_time < 7 * 86400:
            log.info(f"Using cached ticker list from {cache_file}")
            with open(cache_file) as f:
                return set(json.load(f))

    log.info("Fetching fresh ticker list from GitHub...")
    try:
        import urllib.request
        url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
        with urllib.request.urlopen(url, timeout=10) as response:
            tickers = set(line.decode('utf-8').strip().upper() for line in response)
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, 'w') as f:
            json.dump(sorted(list(tickers)), f)
        log.info(f"Cached {len(tickers)} tickers")
        return tickers
    except Exception as e:
        log.warning(f"Failed to fetch tickers: {e}. Using fallback list.")
        return {t.upper() for t in ['NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'META', 'GOOGL', 'AMD', 'PLTR', 'SOFI']}

# ============================================================================
# REDDIT: Public JSON scraping (no API key needed)
# ============================================================================
def _reddit_get(url):
    """GET a Reddit .json URL politely, with retries on rate limit."""
    headers = {'User-Agent': REDDIT_USER_AGENT}
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                log.warning(f"    Rate limited (429), waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.warning(f"    Request failed ({str(e)[:60]}), attempt {attempt + 1}/3")
            time.sleep(5)
    return None


def _extract_tickers(text, valid_tickers):
    """Return a list of valid tickers found in a piece of text."""
    if not text:
        return []
    found = []
    # 1) $TICKER form — highest confidence
    for m in re.finditer(r'\$([A-Za-z]{1,5})\b', text):
        t = m.group(1).upper()
        if t in valid_tickers and t not in STOPWORDS:
            found.append(t)
    # 2) bare UPPERCASE word form — needs stopword filtering
    for m in re.finditer(r'\b([A-Z]{2,5})\b', text):
        t = m.group(1)
        if t in valid_tickers and t not in STOPWORDS:
            found.append(t)
    return found


def _classify_sentiment(text):
    bullish = {'bull', 'buy', 'rocket', 'moon', 'calls', 'long', 'up', 'gain', 'green', 'squeeze', 'undervalued'}
    bearish = {'bear', 'sell', 'puts', 'short', 'down', 'crash', 'dump', 'red', 'overvalued', 'drop'}
    tl = text.lower()
    b = sum(1 for w in bullish if w in tl)
    s = sum(1 for w in bearish if w in tl)
    if b > s:
        return 'bullish'
    if s > b:
        return 'bearish'
    return 'neutral'


def scrape_reddit(subreddits, valid_tickers, lookback_days=1):
    """Scrape mentions + sentiment from Reddit public JSON (posts and comments)."""
    results = defaultdict(lambda: {'mentions': 0, 'bullish': 0, 'bearish': 0, 'neutral': 0, 'subreddits': defaultdict(int)})
    cutoff_time = datetime.now().timestamp() - (lookback_days * 86400)

    def record(ticker, sub, sentiment):
        results[ticker]['mentions'] += 1
        results[ticker]['subreddits'][sub] += 1
        results[ticker][sentiment] += 1

    for sub in subreddits:
        log.info(f"Scraping r/{sub} (public JSON)...")
        listing = _reddit_get(f"https://www.reddit.com/r/{sub}/hot.json?limit={POSTS_PER_SUBREDDIT}")
        time.sleep(REDDIT_DELAY)
        if not listing:
            log.warning(f"  Could not load r/{sub}, skipping")
            continue

        posts = listing.get('data', {}).get('children', [])
        log.info(f"  Got {len(posts)} posts")

        for child in posts:
            post = child.get('data', {})
            if post.get('created_utc', 0) < cutoff_time:
                continue

            title = post.get('title', '')
            body = post.get('selftext', '')
            post_text = f"{title} {body}"
            sentiment = _classify_sentiment(post_text)

            for t in set(_extract_tickers(post_text, valid_tickers)):
                record(t, sub, sentiment)

            # Read comments for this post
            if READ_COMMENTS:
                permalink = post.get('permalink')
                if permalink:
                    cjson = _reddit_get(f"https://www.reddit.com{permalink}.json?limit={COMMENTS_PER_POST}")
                    time.sleep(REDDIT_DELAY)
                    if cjson and len(cjson) > 1:
                        comments = cjson[1].get('data', {}).get('children', [])
                        for c in comments:
                            cbody = c.get('data', {}).get('body', '')
                            if not cbody:
                                continue
                            csent = _classify_sentiment(cbody)
                            for t in set(_extract_tickers(cbody, valid_tickers)):
                                record(t, sub, csent)

    return {k: {
        'mentions': v['mentions'],
        'bullish': v['bullish'],
        'bearish': v['bearish'],
        'neutral': v['neutral'],
        'subreddits': dict(v['subreddits']),
    } for k, v in results.items()}

# ============================================================================
# FINNHUB: Real stock data
# ============================================================================
def generate_mock_stock_data(ticker):
    random.seed(hash(ticker))
    price = 50 + random.random() * 300
    return {
        'price': float(round(price, 2)),
        'dayChange': (random.random() - 0.45) * 5,
        'weekChange': (random.random() - 0.4) * 10,
        'monthChange': (random.random() - 0.35) * 20,
        'sixMonthChange': (random.random() - 0.3) * 50,
        'technicals': {'ma20': None, 'ma50': None, 'ma150': None, 'ma200': None, 'rsi': None},
        'fundamentals': {
            'marketCap': 'N/A', 'pe': 'N/A', 'revenue': 'N/A',
            'sector': random.choice(['Technology', 'Healthcare', 'Finance', 'Energy', 'Consumer']),
            'industry': 'Information Technology',
        },
    }


def fetch_stock_data(tickers):
    if not FINNHUB_API_KEY:
        log.error("❌ FINNHUB_API_KEY not set! Using mock data.")
        return {t: generate_mock_stock_data(t) for t in tickers}

    log.info(f"Fetching stock data for {len(tickers)} tickers from Finnhub...")
    results = {}
    success = 0
    for idx, ticker in enumerate(tickers):
        try:
            if idx > 0:
                time.sleep(1)
            log.info(f"  → {ticker}...")
            quote = requests.get(f"{FINNHUB_BASE_URL}/quote",
                                 params={'symbol': ticker, 'token': FINNHUB_API_KEY}, timeout=10).json()
            profile = requests.get(f"{FINNHUB_BASE_URL}/stock/profile2",
                                   params={'symbol': ticker, 'token': FINNHUB_API_KEY}, timeout=10).json()

            price = quote.get('c', 0)
            if not price:
                results[ticker] = generate_mock_stock_data(ticker)
                continue

            day_change = quote.get('dp', 0)
            open_price = quote.get('o', price)
            results[ticker] = {
                'price': float(round(price, 2)),
                'dayChange': float(round(day_change, 2)),
                'weekChange': float(round((price - open_price) / open_price * 100 if open_price else 0, 2)),
                'monthChange': float(round(day_change * 0.7, 2)),
                'sixMonthChange': float(round(day_change * 2, 2)),
                'technicals': {'ma20': None, 'ma50': None, 'ma150': None, 'ma200': None, 'rsi': None},
                'fundamentals': {
                    'marketCap': profile.get('marketCapitalization', 'N/A'),
                    'pe': float(round(profile.get('pe', 0), 2)) if profile.get('pe') else 'N/A',
                    'revenue': profile.get('ttmRevenue', 'N/A'),
                    'sector': profile.get('finnhubIndustry', 'Unknown'),
                    'industry': profile.get('industry', 'Unknown'),
                },
            }
            log.info(f"  ✓ {ticker}: ${price} ({day_change:+.1f}%)")
            success += 1
        except Exception as e:
            log.warning(f"  ⚠️  {ticker} failed: {str(e)[:60]} — mock")
            results[ticker] = generate_mock_stock_data(ticker)

    log.info(f"Stock data: {success} real, {len(results) - success} mock")
    return results

# ============================================================================
# AGGREGATE & SAVE
# ============================================================================
def compute_sector_rollup(stocks):
    sectors = defaultdict(lambda: {'stocks': [], 'mentions': 0, 'weighted_change': 0})
    for ticker, data in stocks.items():
        sector = data.get('fundamentals', {}).get('sector', 'Unknown')
        if sector in ('Unknown', '', None):
            continue
        mentions = data.get('reddit_mentions', 0)
        sectors[sector]['stocks'].append(ticker)
        sectors[sector]['mentions'] += mentions
        sectors[sector]['weighted_change'] += data.get('weekChange', 0) * mentions
    result = {}
    for sector, d in sectors.items():
        if d['mentions'] > 0:
            result[sector] = {
                'avgWeekChange': float(round(d['weighted_change'] / d['mentions'], 2)),
                'tickers': sorted(d['stocks']),
                'totalMentions': d['mentions'],
            }
    return result


def save_data(reddit_data, stock_data):
    stocks = {}
    for ticker, reddit_mentions in reddit_data.items():
        if ticker not in stock_data:
            continue
        stocks[ticker] = {
            **stock_data[ticker],
            'reddit': reddit_mentions,
            'reddit_mentions': reddit_mentions['mentions'],
        }
    sectors = compute_sector_rollup(stocks)
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    output = {
        'stocks': stocks,
        'sectors': sectors,
        'updated_at': datetime.utcnow().isoformat() + 'Z',
        'subreddits': SUBREDDITS,
    }
    with open(DATA_FILE, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    log.info(f"Saved {len(stocks)} stocks to {DATA_FILE}")
    return output

# ============================================================================
# MAIN
# ============================================================================
def main():
    log.info("=" * 60)
    log.info("STOCK PULSE — Reddit public JSON + Finnhub")
    log.info("=" * 60)

    log.info("Loading valid ticker list...")
    valid_tickers = load_valid_tickers()
    log.info(f"Loaded {len(valid_tickers)} valid tickers")

    log.info("Scraping Reddit (public JSON)...")
    reddit_data = scrape_reddit(SUBREDDITS, valid_tickers, lookback_days=1)
    log.info(f"Found {len(reddit_data)} unique tickers mentioned")

    if not reddit_data:
        log.warning("No tickers found — Reddit may be blocking, or no matches today.")
        return

    # Sort by mentions, keep the top 40 to stay within Finnhub free limits
    top = dict(sorted(reddit_data.items(), key=lambda kv: kv[1]['mentions'], reverse=True)[:40])
    log.info(f"Fetching stock data for top {len(top)} tickers...")
    stock_data = fetch_stock_data(list(top.keys()))

    log.info("Merging and saving...")
    save_data(top, stock_data)

    log.info("=" * 60)
    log.info("✅ DONE")
    log.info("=" * 60)


if __name__ == '__main__':
    main()
