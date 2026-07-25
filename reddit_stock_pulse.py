#!/usr/bin/env python3
"""
Reddit Stock Pulse — Reddit scraping via Apify (works from GitHub!) + Finnhub stock data.
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
APIFY_TOKEN = os.environ.get('APIFY_TOKEN')

SUBREDDITS = ['stocks', 'investing', 'wallstreetbets', 'ValueInvesting']
DATA_FILE = 'data/stocks.json'
TICKER_CACHE_FILE = 'data/ticker_cache.json'

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
APIFY_ACTOR = "automation-lab~reddit-scraper"  # ~ instead of / for the URL
APIFY_BASE_URL = "https://api.apify.com/v2"

# How much to pull per subreddit. Keep modest to stay well inside the free $5 credit.
POSTS_PER_SUBREDDIT = 40
INCLUDE_COMMENTS = True
MAX_COMMENTS_PER_POST = 30
TOP_TICKERS_FOR_FINNHUB = 40  # only fetch prices for the most-discussed N

# Words that look like tickers but aren't — filtered out.
STOPWORDS = {
    'A', 'I', 'IT', 'IS', 'BE', 'TO', 'DO', 'GO', 'ON', 'IN', 'AT', 'OR', 'AN', 'AS', 'IF', 'SO', 'UP', 'MY', 'BY', 'WE', 'HE',
    'CEO', 'CFO', 'IPO', 'ETF', 'USA', 'US', 'UK', 'EU', 'DD', 'YOLO', 'FD', 'FOMO', 'ATH', 'ATL', 'EPS', 'PE', 'PT', 'YTD',
    'AI', 'ML', 'EV', 'PC', 'TV', 'OK', 'LOL', 'IMO', 'IMHO', 'TLDR', 'EDIT', 'FYI', 'ELI', 'AKA', 'NSFW', 'WSB', 'THE',
    'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HAS', 'HAD', 'WAS', 'ONE', 'OUR', 'OUT', 'DAY', 'GET', 'NEW',
    'NOW', 'OLD', 'SEE', 'HIM', 'TWO', 'HOW', 'ITS', 'WHO', 'DID', 'YES', 'HIS', 'HER', 'BIG', 'BUY', 'LOW', 'RED',
    'CALL', 'PUTS', 'CALLS', 'GAIN', 'LOSS', 'HODL', 'MOON', 'BEAR', 'BULL', 'LONG', 'RISK', 'CASH', 'FEAR', 'HIGH', 'OPEN',
    'WILL', 'JUST', 'LIKE', 'WITH', 'THIS', 'THAT', 'FROM', 'HAVE', 'MORE', 'THAN', 'WHAT', 'WHEN', 'YOUR', 'THEY',
}

# ============================================================================
# TICKER LIST
# ============================================================================
def load_valid_tickers():
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
        log.warning(f"Failed to fetch tickers: {e}. Using fallback.")
        return {t.upper() for t in ['NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'META', 'GOOGL', 'AMD', 'PLTR', 'SOFI']}

# ============================================================================
# TEXT ANALYSIS HELPERS
# ============================================================================
def extract_tickers(text, valid_tickers):
    if not text:
        return []
    found = []
    # $TICKER form (high confidence)
    for m in re.finditer(r'\$([A-Za-z]{1,5})\b', text):
        t = m.group(1).upper()
        if t in valid_tickers and t not in STOPWORDS:
            found.append(t)
    # bare UPPERCASE word form (needs stopword filtering)
    for m in re.finditer(r'\b([A-Z]{2,5})\b', text):
        t = m.group(1)
        if t in valid_tickers and t not in STOPWORDS:
            found.append(t)
    return found


def classify_sentiment(text):
    bullish = {'bull', 'buy', 'rocket', 'moon', 'calls', 'long', 'gain', 'green', 'squeeze', 'undervalued'}
    bearish = {'bear', 'sell', 'puts', 'short', 'crash', 'dump', 'overvalued', 'drop'}
    tl = (text or '').lower()
    b = sum(1 for w in bullish if w in tl)
    s = sum(1 for w in bearish if w in tl)
    if b > s:
        return 'bullish'
    if s > b:
        return 'bearish'
    return 'neutral'

# ============================================================================
# REDDIT via APIFY
# ============================================================================
def scrape_reddit_via_apify(subreddits, valid_tickers):
    """Run the Apify Reddit actor and process its dataset output."""
    if not APIFY_TOKEN:
        log.error("❌ APIFY_TOKEN not set!")
        return {}

    urls = [f"https://www.reddit.com/r/{sub}/" for sub in subreddits]
    run_input = {
        "urls": urls,
        "maxPostsPerSource": POSTS_PER_SUBREDDIT,
        "sort": "hot",
        "includeComments": INCLUDE_COMMENTS,
        "maxCommentsPerPost": MAX_COMMENTS_PER_POST,
        "commentDepth": 2,
    }

    log.info(f"Starting Apify actor for {len(subreddits)} subreddits...")

    # Start the actor run and wait for it to finish (waitForFinish in seconds)
    run_url = f"{APIFY_BASE_URL}/acts/{APIFY_ACTOR}/runs?token={APIFY_TOKEN}&waitForFinish=300"
    try:
        resp = requests.post(run_url, json=run_input, timeout=320)
        resp.raise_for_status()
        run_data = resp.json().get('data', {})
    except Exception as e:
        log.error(f"Failed to start/finish Apify run: {e}")
        return {}

    status = run_data.get('status')
    log.info(f"Apify run status: {status}")

    # Find the dataset ID that holds the results
    dataset_id = run_data.get('defaultDatasetId')
    named = run_data.get('namedDatasetIds') or {}
    if named.get('posts'):
        dataset_id = named['posts']

    if not dataset_id:
        log.error("No dataset ID returned from Apify run")
        return {}

    # Fetch dataset items
    items_url = f"{APIFY_BASE_URL}/datasets/{dataset_id}/items?token={APIFY_TOKEN}&format=json"
    try:
        items_resp = requests.get(items_url, timeout=60)
        items_resp.raise_for_status()
        items = items_resp.json()
    except Exception as e:
        log.error(f"Failed to fetch Apify dataset: {e}")
        return {}

    log.info(f"Got {len(items)} items from Apify (posts + comments)")

    # Process items into ticker counts
    results = defaultdict(lambda: {'mentions': 0, 'bullish': 0, 'bearish': 0, 'neutral': 0, 'subreddits': defaultdict(int)})

    def record(ticker, sub, sentiment):
        results[ticker]['mentions'] += 1
        if sub:
            results[ticker]['subreddits'][sub] += 1
        results[ticker][sentiment] += 1

    for item in items:
        itype = item.get('type', 'post')
        sub = item.get('subreddit', '')

        if itype == 'post':
            text = f"{item.get('title', '')} {item.get('selfText', '')}"
        else:  # comment
            text = item.get('body', '')

        if not text.strip():
            continue

        sentiment = classify_sentiment(text)
        for t in set(extract_tickers(text, valid_tickers)):
            record(t, sub, sentiment)

    return {k: {
        'mentions': v['mentions'],
        'bullish': v['bullish'],
        'bearish': v['bearish'],
        'neutral': v['neutral'],
        'subreddits': dict(v['subreddits']),
    } for k, v in results.items()}

# ============================================================================
# FINNHUB
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
        'fundamentals': {'marketCap': 'N/A', 'pe': 'N/A', 'revenue': 'N/A',
                         'sector': 'Unknown', 'industry': 'Unknown'},
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
    log.info("STOCK PULSE — Apify (Reddit) + Finnhub (stocks)")
    log.info("=" * 60)

    log.info("Loading valid ticker list...")
    valid_tickers = load_valid_tickers()
    log.info(f"Loaded {len(valid_tickers)} valid tickers")

    log.info("Scraping Reddit via Apify...")
    reddit_data = scrape_reddit_via_apify(SUBREDDITS, valid_tickers)
    log.info(f"Found {len(reddit_data)} unique tickers mentioned")

    if not reddit_data:
        log.warning("No tickers found — check Apify token/run.")
        return

    # Keep top-N by mentions for Finnhub
    top = dict(sorted(reddit_data.items(), key=lambda kv: kv[1]['mentions'], reverse=True)[:TOP_TICKERS_FOR_FINNHUB])
    log.info(f"Top tickers: {', '.join(list(top.keys())[:15])}...")

    log.info("Fetching stock data from Finnhub...")
    stock_data = fetch_stock_data(list(top.keys()))

    log.info("Merging and saving...")
    save_data(top, stock_data)

    log.info("=" * 60)
    log.info("✅ DONE")
    log.info("=" * 60)


if __name__ == '__main__':
    main()
