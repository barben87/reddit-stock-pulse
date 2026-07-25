#!/usr/bin/env python3
"""
Reddit Stock Pulse v2
  - Reddit via Apify (last 24h)
  - Finnhub: current price + daily change for ALL discussed tickers (free, 60/min)
  - Alpha Vantage: full history -> chart series + MA20/50/150/200 for top tickers & sector ETFs (free, 25/day)
  - Daily snapshots -> "most discussed in last 7 days"
Runs in GitHub Actions once daily.
"""

import os
import json
import re
import random
import time
from datetime import datetime, timedelta, timezone
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
ALPHAVANTAGE_API_KEY = os.environ.get('ALPHAVANTAGE_API_KEY')

SUBREDDITS = ['stocks', 'investing', 'wallstreetbets', 'ValueInvesting']

DATA_FILE = 'data/stocks.json'
TICKER_CACHE_FILE = 'data/ticker_cache.json'
HISTORY_DIR = 'data/history'          # daily snapshots for the 7-day view
AV_CACHE_FILE = 'data/av_cache.json'  # cached Alpha Vantage series (avoid re-fetching)

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
APIFY_ACTOR = "automation-lab~reddit-scraper"
APIFY_BASE_URL = "https://api.apify.com/v2"
AV_BASE_URL = "https://www.alphavantage.co/query"

# Reddit pull sizing (larger to catch big discussion threads where most mentions live)
POSTS_PER_SUBREDDIT = 60
INCLUDE_COMMENTS = True
MAX_COMMENTS_PER_POST = 80
LOOKBACK_HOURS = 48

# Alpha Vantage budget (free tier: 25/day, 5/min)
AV_DAILY_BUDGET = 25
AV_TOP_STOCKS = 14     # how many top stocks get a full chart+MA each day
AV_CACHE_TTL_DAYS = 3         # reuse a symbol's AV series for this many days
AV_MIN_DELAY = 13             # seconds between AV calls (5/min -> 12s min; 13 for safety)

# Sector ETFs (the 11 SPDR sector ETFs + a couple extras). name -> ETF ticker
SECTOR_ETFS = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Energy": "XLE",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}

STOPWORDS = {
    'A','I','IT','IS','BE','TO','DO','GO','ON','IN','AT','OR','AN','AS','IF','SO','UP','MY','BY','WE','HE',
    'CEO','CFO','IPO','ETF','USA','US','UK','EU','DD','YOLO','FD','FOMO','ATH','ATL','EPS','PE','PT','YTD',
    'AI','ML','EV','PC','TV','OK','LOL','IMO','IMHO','TLDR','EDIT','FYI','ELI','AKA','NSFW','WSB','THE',
    'AND','FOR','ARE','BUT','NOT','YOU','ALL','CAN','HAS','HAD','WAS','ONE','OUR','OUT','DAY','GET','NEW',
    'NOW','OLD','SEE','HIM','TWO','HOW','ITS','WHO','DID','YES','HIS','HER','BIG','BUY','LOW','RED',
    'CALL','PUTS','CALLS','GAIN','LOSS','HODL','MOON','BEAR','BULL','LONG','RISK','CASH','FEAR','HIGH','OPEN',
    'WILL','JUST','LIKE','WITH','THIS','THAT','FROM','HAVE','MORE','THAN','WHAT','WHEN','YOUR','THEY',
}

# ============================================================================
# TICKER LIST
# ============================================================================
def load_valid_tickers():
    cache_file = TICKER_CACHE_FILE
    if os.path.exists(cache_file):
        if datetime.now().timestamp() - os.path.getmtime(cache_file) < 7 * 86400:
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
        return {t.upper() for t in ['NVDA','TSLA','AAPL','MSFT','AMZN','META','GOOGL','AMD','PLTR','SOFI']}

# ============================================================================
# TEXT ANALYSIS
# ============================================================================
def extract_tickers(text, valid_tickers):
    if not text:
        return []
    found = []
    for m in re.finditer(r'\$([A-Za-z]{1,5})\b', text):
        t = m.group(1).upper()
        if t in valid_tickers and t not in STOPWORDS:
            found.append(t)
    for m in re.finditer(r'\b([A-Z]{2,5})\b', text):
        t = m.group(1)
        if t in valid_tickers and t not in STOPWORDS:
            found.append(t)
    return found

def classify_sentiment(text):
    bullish = {'bull','buy','rocket','moon','calls','long','gain','green','squeeze','undervalued'}
    bearish = {'bear','sell','puts','short','crash','dump','overvalued','drop'}
    tl = (text or '').lower()
    b = sum(1 for w in bullish if w in tl)
    s = sum(1 for w in bearish if w in tl)
    return 'bullish' if b > s else 'bearish' if s > b else 'neutral'

# ============================================================================
# REDDIT via APIFY (last 24h)
# ============================================================================
def scrape_reddit_via_apify(subreddits, valid_tickers):
    if not APIFY_TOKEN:
        log.error("❌ APIFY_TOKEN not set!")
        return {}

    urls = [f"https://www.reddit.com/r/{sub}/" for sub in subreddits]
    run_input = {
        "urls": urls,
        "maxPostsPerSource": POSTS_PER_SUBREDDIT,
        "sort": "new",  # 'new' so we can filter by recency (last 24h)
        "includeComments": INCLUDE_COMMENTS,
        "maxCommentsPerPost": MAX_COMMENTS_PER_POST,
        "commentDepth": 2,
    }

    log.info(f"Starting Apify actor for {len(subreddits)} subreddits (last {LOOKBACK_HOURS}h)...")
    run_url = f"{APIFY_BASE_URL}/acts/{APIFY_ACTOR}/runs?token={APIFY_TOKEN}&waitForFinish=300"
    try:
        resp = requests.post(run_url, json=run_input, timeout=320)
        resp.raise_for_status()
        run_data = resp.json().get('data', {})
    except Exception as e:
        log.error(f"Failed Apify run: {e}")
        return {}

    log.info(f"Apify run status: {run_data.get('status')}")
    dataset_id = run_data.get('defaultDatasetId')
    named = run_data.get('namedDatasetIds') or {}
    if named.get('posts'):
        dataset_id = named['posts']
    if not dataset_id:
        log.error("No dataset ID from Apify")
        return {}

    try:
        items = requests.get(
            f"{APIFY_BASE_URL}/datasets/{dataset_id}/items?token={APIFY_TOKEN}&format=json",
            timeout=60).json()
    except Exception as e:
        log.error(f"Failed to fetch Apify dataset: {e}")
        return {}

    log.info(f"Got {len(items)} items from Apify")

    # Diagnostic: show the keys of the first post and first comment so we can
    # verify field names (subreddit, createdAt, etc.) against reality.
    if items:
        first_post = next((it for it in items if it.get('type', 'post') == 'post'), None)
        first_comment = next((it for it in items if it.get('type') == 'comment'), None)
        if first_post:
            log.info(f"  POST fields: {sorted(first_post.keys())}")
            log.info(f"  POST subreddit sample: '{first_post.get('subreddit')}' | url: '{(first_post.get('permalink') or first_post.get('url') or '')[:60]}'")
        if first_comment:
            log.info(f"  COMMENT fields: {sorted(first_comment.keys())}")

    n_posts = sum(1 for it in items if it.get('type', 'post') == 'post')
    n_comments = len(items) - n_posts
    log.info(f"  Breakdown: {n_posts} posts, {n_comments} comments")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    results = defaultdict(lambda: {'mentions':0,'bullish':0,'bearish':0,'neutral':0,'subreddits':defaultdict(int)})

    def parse_dt(s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace('Z', '+00:00'))
        except Exception:
            return None

    kept = 0
    for item in items:
        created = parse_dt(item.get('createdAt'))
        # Only enforce recency on posts; comments inherit their post's thread
        if item.get('type', 'post') == 'post' and created and created < cutoff:
            continue
        kept += 1

        # --- Robust subreddit attribution ---
        # Apify items may expose the subreddit under different keys, or only in a URL/permalink.
        sub = (item.get('subreddit') or item.get('subredditName')
               or item.get('community') or '')
        if not sub:
            link = item.get('permalink') or item.get('url') or item.get('postUrl') or ''
            m = re.search(r'/r/([A-Za-z0-9_]+)', link)
            if m:
                sub = m.group(1)
        # Normalize to our canonical subreddit names (case-insensitive match)
        if sub:
            for canonical in SUBREDDITS:
                if sub.lower() == canonical.lower():
                    sub = canonical
                    break

        if item.get('type', 'post') == 'post':
            text = f"{item.get('title','')} {item.get('selfText','')}"
        else:
            text = item.get('body', '')
        if not text.strip():
            continue

        sentiment = classify_sentiment(text)
        tickers_in_text = extract_tickers(text, valid_tickers)
        if not tickers_in_text:
            continue
        # Count each distinct ticker once per item, but weight posts a bit higher
        # than comments (a post mentioning a ticker is a stronger signal than one comment).
        weight = 2 if item.get('type', 'post') == 'post' else 1
        for t in set(tickers_in_text):
            results[t]['mentions'] += weight
            if sub:
                results[t]['subreddits'][sub] += weight
            results[t][sentiment] += 1

    log.info(f"Kept {kept} items within {LOOKBACK_HOURS}h window")
    return {k: {
        'mentions': v['mentions'], 'bullish': v['bullish'], 'bearish': v['bearish'],
        'neutral': v['neutral'], 'subreddits': dict(v['subreddits']),
    } for k, v in results.items()}

# ============================================================================
# FINNHUB — current price + day change (for everyone)
# ============================================================================
def fetch_finnhub_quotes(tickers):
    results = {}
    if not FINNHUB_API_KEY:
        log.error("❌ FINNHUB_API_KEY not set!")
        return {t: None for t in tickers}
    log.info(f"Finnhub: fetching quotes for {len(tickers)} tickers...")
    for idx, ticker in enumerate(tickers):
        try:
            if idx > 0:
                time.sleep(1)
            quote = requests.get(f"{FINNHUB_BASE_URL}/quote",
                                 params={'symbol': ticker, 'token': FINNHUB_API_KEY}, timeout=10).json()
            profile = requests.get(f"{FINNHUB_BASE_URL}/stock/profile2",
                                   params={'symbol': ticker, 'token': FINNHUB_API_KEY}, timeout=10).json()
            price = quote.get('c', 0)
            if not price:
                results[ticker] = None
                continue
            results[ticker] = {
                'price': float(round(price, 2)),
                'dayChange': float(round(quote.get('dp', 0), 2)),
                'fundamentals': {
                    'marketCap': profile.get('marketCapitalization', 'N/A'),
                    'pe': float(round(profile.get('pe', 0), 2)) if profile.get('pe') else 'N/A',
                    'sector': profile.get('finnhubIndustry', 'Unknown'),
                    'industry': profile.get('finnhubIndustry', 'Unknown'),
                },
            }
        except Exception as e:
            log.warning(f"  Finnhub {ticker} failed: {str(e)[:50]}")
            results[ticker] = None
    ok = sum(1 for v in results.values() if v)
    log.info(f"Finnhub: {ok}/{len(tickers)} quotes OK")
    return results

# ============================================================================
# ALPHA VANTAGE — full daily history -> chart + moving averages
# ============================================================================
def load_av_cache():
    if os.path.exists(AV_CACHE_FILE):
        try:
            with open(AV_CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_av_cache(cache):
    os.makedirs(os.path.dirname(AV_CACHE_FILE), exist_ok=True)
    with open(AV_CACHE_FILE, 'w') as f:
        json.dump(cache, f)

def _sma(values, window):
    if len(values) < window:
        return None
    return round(sum(values[-window:]) / window, 2)

def _pct(a, b):
    return round((b - a) / a * 100, 2) if a else 0

def compute_series_metrics(closes):
    """closes = list of daily closes, OLD->NEW. Returns chart points + MAs + period changes."""
    if not closes:
        return None
    last = closes[-1]
    def change_days(n):
        if len(closes) > n:
            return _pct(closes[-n-1], last)
        return _pct(closes[0], last)
    # sample the chart (keep it light): last 180 trading days
    series = closes[-180:]
    return {
        'series': [round(c, 2) for c in series],
        'ma20': _sma(closes, 20),
        'ma50': _sma(closes, 50),
        'ma150': _sma(closes, 150),
        'ma200': _sma(closes, 200),
        'weekChange': change_days(5),
        'monthChange': change_days(21),
        'sixMonthChange': change_days(126),
    }

def av_fetch_daily(symbol, budget_state):
    """Fetch full daily history from Alpha Vantage, respecting the daily budget + cache."""
    cache = budget_state['cache']
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # Use cache if fresh enough
    entry = cache.get(symbol)
    if entry:
        age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(entry['fetched'])).days
        if age_days < AV_CACHE_TTL_DAYS:
            return entry['metrics']

    # Budget check
    if budget_state['used'] >= AV_DAILY_BUDGET:
        return entry['metrics'] if entry else None  # fall back to stale cache if any

    try:
        if budget_state['used'] > 0:
            time.sleep(AV_MIN_DELAY)
        log.info(f"  AV: fetching {symbol} ({budget_state['used']+1}/{AV_DAILY_BUDGET})...")
        r = requests.get(AV_BASE_URL, params={
            'function': 'TIME_SERIES_DAILY',
            'symbol': symbol,
            'outputsize': 'full',
            'apikey': ALPHAVANTAGE_API_KEY,
        }, timeout=30)
        budget_state['used'] += 1
        data = r.json()

        ts = data.get('Time Series (Daily)')
        if not ts:
            note = data.get('Note') or data.get('Information') or data.get('Error Message') or 'no data'
            log.warning(f"  AV {symbol}: {str(note)[:80]}")
            return entry['metrics'] if entry else None

        # sort OLD -> NEW
        dates = sorted(ts.keys())
        closes = [float(ts[d]['4. close']) for d in dates]
        metrics = compute_series_metrics(closes)

        cache[symbol] = {'fetched': datetime.now(timezone.utc).isoformat(), 'metrics': metrics}
        return metrics
    except Exception as e:
        log.warning(f"  AV {symbol} error: {str(e)[:60]}")
        return entry['metrics'] if entry else None

# ============================================================================
# 7-DAY HISTORY (snapshots)
# ============================================================================
def save_daily_snapshot(reddit_data):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    snap = {t: d['mentions'] for t, d in reddit_data.items()}
    with open(f"{HISTORY_DIR}/{today}.json", 'w') as f:
        json.dump({'date': today, 'mentions': snap}, f)
    log.info(f"Saved daily snapshot: {today}")

def compute_7day_top():
    if not os.path.isdir(HISTORY_DIR):
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    totals = defaultdict(int)
    for fname in os.listdir(HISTORY_DIR):
        if not fname.endswith('.json'):
            continue
        try:
            date = datetime.strptime(fname[:-5], '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if date < cutoff:
            continue
        with open(f"{HISTORY_DIR}/{fname}") as f:
            snap = json.load(f)
        for t, m in snap.get('mentions', {}).items():
            totals[t] += m
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return [{'ticker': t, 'mentions7d': m} for t, m in ranked[:20]]

# ============================================================================
# MERGE & SAVE
# ============================================================================
def build_output(reddit_data, quotes, av_metrics, sector_data, top7):
    stocks = {}
    for ticker, rd in reddit_data.items():
        q = quotes.get(ticker)
        if not q:
            continue
        av = av_metrics.get(ticker, {}) or {}
        stocks[ticker] = {
            'price': q['price'],
            'dayChange': q['dayChange'],
            'weekChange': av.get('weekChange'),
            'monthChange': av.get('monthChange'),
            'sixMonthChange': av.get('sixMonthChange'),
            'series': av.get('series'),
            'technicals': {
                'ma20': av.get('ma20'), 'ma50': av.get('ma50'),
                'ma150': av.get('ma150'), 'ma200': av.get('ma200'),
            },
            'fundamentals': q['fundamentals'],
            'reddit': rd,
            'reddit_mentions': rd['mentions'],
        }

    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    output = {
        'stocks': stocks,
        'sectors': sector_data,
        'topToday': sorted(
            [{'ticker': t, 'mentions': d['mentions']} for t, d in reddit_data.items() if t in stocks],
            key=lambda x: x['mentions'], reverse=True)[:20],
        'top7Days': top7,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'subreddits': SUBREDDITS,
    }
    with open(DATA_FILE, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    log.info(f"Saved {len(stocks)} stocks + {len(sector_data)} sectors to {DATA_FILE}")

# ============================================================================
# MAIN
# ============================================================================
def main():
    log.info("=" * 60)
    log.info("STOCK PULSE v2 — Apify + Finnhub + Alpha Vantage")
    log.info("=" * 60)

    valid_tickers = load_valid_tickers()
    log.info(f"Loaded {len(valid_tickers)} valid tickers")

    # 1) Reddit (last 24h)
    reddit_data = scrape_reddit_via_apify(SUBREDDITS, valid_tickers)
    log.info(f"Found {len(reddit_data)} unique tickers")
    if not reddit_data:
        log.warning("No tickers found — stopping.")
        return

    # 2) Daily snapshot + 7-day rollup
    save_daily_snapshot(reddit_data)
    top7 = compute_7day_top()
    log.info(f"7-day top: {', '.join(t['ticker'] for t in top7[:10])}")

    # 3) Finnhub quotes for ALL discussed tickers (cap to 50 to be safe)
    discussed = [t for t, _ in sorted(reddit_data.items(), key=lambda kv: kv[1]['mentions'], reverse=True)][:50]
    quotes = fetch_finnhub_quotes(discussed)

    # 4) Alpha Vantage — budget-limited: sector ETFs first, then top stocks
    budget_state = {'used': 0, 'cache': load_av_cache()}
    av_metrics = {}

    # 4a) sector ETFs (trend)
    sector_data = {}
    if ALPHAVANTAGE_API_KEY:
        log.info("Alpha Vantage: sector ETFs...")
        for sector_name, etf in SECTOR_ETFS.items():
            m = av_fetch_daily(etf, budget_state)
            if m:
                sector_data[sector_name] = {
                    'etf': etf,
                    'price': m['series'][-1] if m.get('series') else None,
                    'weekChange': m.get('weekChange'),
                    'monthChange': m.get('monthChange'),
                    'sixMonthChange': m.get('sixMonthChange'),
                    'series': m.get('series'),
                }
    else:
        log.warning("ALPHAVANTAGE_API_KEY not set — skipping charts & ETF trends")

    # 4b) top discussed stocks get full chart + MA (whatever budget remains)
    if ALPHAVANTAGE_API_KEY:
        log.info("Alpha Vantage: top discussed stocks...")
        for ticker in discussed[:AV_TOP_STOCKS]:
            if budget_state['used'] >= AV_DAILY_BUDGET:
                log.info("  AV daily budget reached — remaining stocks use Finnhub-only.")
                break
            m = av_fetch_daily(ticker, budget_state)
            if m:
                av_metrics[ticker] = m

    save_av_cache(budget_state['cache'])

    # 5) merge & save
    build_output(reddit_data, quotes, av_metrics, sector_data, top7)

    log.info("=" * 60)
    log.info("✅ DONE")
    log.info("=" * 60)


if __name__ == '__main__':
    main()
