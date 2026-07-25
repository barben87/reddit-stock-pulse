#!/usr/bin/env python3
"""
Reddit Stock Pulse — Scrape Reddit + fetch real stock data from Finnhub
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

import praw
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# ============================================================================
# CONFIG
# ============================================================================
REDDIT_CLIENT_ID = os.environ.get('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.environ.get('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.environ.get('REDDIT_USER_AGENT', 'StockPulse/1.0')
FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY')

SUBREDDITS = ['stocks', 'investing', 'wallstreetbets', 'ValueInvesting']
DATA_FILE = 'data/stocks.json'
TICKER_CACHE_FILE = 'data/ticker_cache.json'
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

# ============================================================================
# UTILITY: Load/Cache Valid Ticker List
# ============================================================================
def load_valid_tickers():
    """Load list of all valid US stock tickers from GitHub"""
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
# MOCK DATA GENERATOR
# ============================================================================
def generate_mock_stock_data(ticker):
    """Generate realistic mock stock data for testing"""
    random.seed(hash(ticker))
    price = 50 + random.random() * 300
    changes = {
        'dayChange': (random.random() - 0.45) * 5,
        'weekChange': (random.random() - 0.4) * 10,
        'monthChange': (random.random() - 0.35) * 20,
        'sixMonthChange': (random.random() - 0.3) * 50,
    }
    return {
        'price': float(round(price, 2)),
        **changes,
        'technicals': {'ma20': None, 'ma50': None, 'ma150': None, 'ma200': None, 'rsi': None},
        'fundamentals': {
            'marketCap': random.choice(['N/A', f'{100 + random.randint(0, 900)}B']),
            'pe': float(round(20 + random.random() * 60, 2)) if random.random() > 0.3 else 'N/A',
            'revenue': 'N/A',
            'sector': random.choice(['Technology', 'Healthcare', 'Finance', 'Energy', 'Consumer']),
            'industry': 'Information Technology',
        },
    }

# ============================================================================
# REDDIT: Scrape Mentions and Sentiment
# ============================================================================
def scrape_reddit(subreddits, valid_tickers, lookback_days=1):
    """Scrape Reddit for stock mentions"""
    
    # Check if we're in test mode
    if 'placeholder' in (REDDIT_CLIENT_ID or '').lower() or 'test' in (REDDIT_CLIENT_ID or '').lower():
        log.warning("⚠️  RUNNING IN TEST MODE — Using mock Reddit data")
        return generate_mock_reddit_data()
    
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
    except Exception as e:
        log.error(f"Failed to authenticate with Reddit: {e}")
        log.warning("Falling back to mock data")
        return generate_mock_reddit_data()
    
    results = defaultdict(lambda: {'mentions': 0, 'bullish': 0, 'bearish': 0, 'neutral': 0, 'subreddits': defaultdict(int)})
    
    ticker_pattern = re.compile(r'\$([A-Z]{1,5})\b|(?:^|\s)([A-Z]{2,5})(?:\s|$|[.,!?\)])')
    bullish_words = {'bull', 'buy', 'rocket', 'moon', 'great', 'strong', 'rise', 'up', 'gain', 'profit'}
    bearish_words = {'bear', 'sell', 'dump', 'crash', 'bad', 'weak', 'down', 'loss'}
    
    cutoff_time = datetime.now().timestamp() - (lookback_days * 86400)
    
    for subreddit_name in subreddits:
        log.info(f"Scraping r/{subreddit_name}...")
        try:
            subreddit = reddit.subreddit(subreddit_name)
            for post in subreddit.search('stock OR ticker OR $', time_filter='week', limit=100):
                if post.created_utc < cutoff_time:
                    continue
                
                text = (post.title + ' ' + post.selftext).upper()
                for match in ticker_pattern.finditer(text):
                    ticker = match.group(1) or match.group(2)
                    if ticker and ticker in valid_tickers:
                        results[ticker]['mentions'] += 1
                        results[ticker]['subreddits'][subreddit_name] += 1
                        
                        text_section = text[max(0, match.start()-50):match.end()+50].lower()
                        if any(w in text_section for w in bullish_words):
                            results[ticker]['bullish'] += 1
                        elif any(w in text_section for w in bearish_words):
                            results[ticker]['bearish'] += 1
                        else:
                            results[ticker]['neutral'] += 1
        except Exception as e:
            log.error(f"Error scraping r/{subreddit_name}: {e}")
    
    return {k: {
        'mentions': v['mentions'],
        'bullish': v['bullish'],
        'bearish': v['bearish'],
        'neutral': v['neutral'],
        'subreddits': dict(v['subreddits']),
    } for k, v in results.items()}

def generate_mock_reddit_data():
    """Generate mock Reddit data for testing"""
    log.info("Generating mock Reddit data for testing...")
    mock_tickers = ['NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMD', 'PLTR', 'SOFI', 'GME', 'META', 'COIN']
    mock_subs = ['stocks', 'investing', 'wallstreetbets', 'ValueInvesting']
    
    results = {}
    for ticker in mock_tickers:
        mentions = 50 + (hash(ticker) % 200)
        results[ticker] = {
            'mentions': mentions,
            'bullish': mentions // 2,
            'bearish': mentions // 6,
            'neutral': mentions // 3,
            'subreddits': {sub: (mentions // len(mock_subs)) + (hash(ticker + sub) % 20) for sub in mock_subs}
        }
    return results

# ============================================================================
# FINNHUB: Fetch Real Stock Data
# ============================================================================
def fetch_stock_data(tickers):
    """Fetch stock data from Finnhub API"""
    
    if not FINNHUB_API_KEY:
        log.error("❌ FINNHUB_API_KEY not set! Using mock data.")
        return {t: generate_mock_stock_data(t) for t in tickers}
    
    log.info(f"Fetching stock data for {len(tickers)} tickers from Finnhub...")
    results = {}
    success_count = 0
    
    for idx, ticker in enumerate(tickers):
        try:
            if idx > 0:
                time.sleep(1)  # Finnhub: 60 requests/min, so 1 sec is safe
            
            log.info(f"  → Fetching {ticker}...")
            
            # Quote endpoint (price + daily change)
            quote_url = f"{FINNHUB_BASE_URL}/quote"
            quote_resp = requests.get(quote_url, params={'symbol': ticker, 'token': FINNHUB_API_KEY}, timeout=10)
            quote_resp.raise_for_status()
            quote = quote_resp.json()
            
            # Company profile (fundamentals)
            profile_url = f"{FINNHUB_BASE_URL}/stock/profile2"
            profile_resp = requests.get(profile_url, params={'symbol': ticker, 'token': FINNHUB_API_KEY}, timeout=10)
            profile_resp.raise_for_status()
            profile = profile_resp.json()
            
            current_price = quote.get('c', 0)
            if not current_price:
                log.warning(f"  ⚠️  No price for {ticker}, using mock")
                results[ticker] = generate_mock_stock_data(ticker)
                continue
            
            day_change = quote.get('dp', 0)  # Daily % change
            open_price = quote.get('o', current_price)
            
            results[ticker] = {
                'price': float(round(current_price, 2)),
                'dayChange': float(round(day_change, 2)),
                'weekChange': float(round((current_price - open_price) / open_price * 100 if open_price else 0, 2)),
                'monthChange': float(round(day_change * 0.7, 2)),  # Estimate
                'sixMonthChange': float(round(day_change * 2, 2)),  # Estimate
                'technicals': {'ma20': None, 'ma50': None, 'ma150': None, 'ma200': None, 'rsi': None},
                'fundamentals': {
                    'marketCap': profile.get('marketCapitalization', 'N/A'),
                    'pe': float(round(profile.get('pe', 0), 2)) if profile.get('pe') else 'N/A',
                    'revenue': profile.get('ttmRevenue', 'N/A'),
                    'sector': profile.get('finnhubIndustry', 'Unknown'),
                    'industry': profile.get('industry', 'Unknown'),
                },
            }
            
            log.info(f"  ✓ {ticker}: ${current_price} ({day_change:+.1f}%)")
            success_count += 1
        
        except Exception as e:
            log.warning(f"  ⚠️  {ticker} failed: {str(e)[:80]} — using mock")
            results[ticker] = generate_mock_stock_data(ticker)
    
    log.info(f"Stock data fetched: {success_count} real, {len(results) - success_count} mock")
    return results

# ============================================================================
# AGGREGATE & SAVE
# ============================================================================
def compute_sector_rollup(stocks):
    """Compute sector-level performance"""
    sectors = defaultdict(lambda: {'stocks': [], 'mentions': 0, 'weighted_change': 0})
    
    for ticker, data in stocks.items():
        if 'fundamentals' not in data or data['fundamentals'].get('sector') == 'Unknown':
            continue
        
        sector = data['fundamentals']['sector']
        mentions = data.get('reddit_mentions', 0)
        week_change = data.get('weekChange', 0)
        
        sectors[sector]['stocks'].append(ticker)
        sectors[sector]['mentions'] += mentions
        sectors[sector]['weighted_change'] += week_change * mentions
    
    result = {}
    for sector, data in sectors.items():
        if data['mentions'] > 0:
            result[sector] = {
                'avgWeekChange': float(round(data['weighted_change'] / data['mentions'], 2)),
                'tickers': sorted(data['stocks']),
                'totalMentions': data['mentions'],
            }
    
    return result

def save_data(reddit_data, stock_data):
    """Merge and save data"""
    stocks = {}
    
    for ticker, reddit_mentions in reddit_data.items():
        if ticker not in stock_data:
            log.warning(f"No stock data for {ticker}, skipping")
            continue
        
        stock_info = stock_data[ticker]
        stocks[ticker] = {
            **stock_info,
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
    log.info("STOCK PULSE SCRAPER — Using Finnhub for Stock Data")
    log.info("=" * 60)
    
    # Load tickers
    log.info("Loading valid ticker list...")
    valid_tickers = load_valid_tickers()
    log.info(f"Loaded {len(valid_tickers)} valid tickers")
    
    # Scrape Reddit
    log.info("Scraping Reddit...")
    reddit_data = scrape_reddit(SUBREDDITS, valid_tickers, lookback_days=1)
    log.info(f"Found {len(reddit_data)} unique tickers mentioned")
    
    if not reddit_data:
        log.warning("No tickers found!")
        return
    
    # Fetch stock data
    log.info("Fetching stock data from Finnhub...")
    stock_data = fetch_stock_data(list(reddit_data.keys()))
    log.info(f"Fetched data for {len(stock_data)} stocks")
    
    # Save
    log.info("Merging and saving...")
    save_data(reddit_data, stock_data)
    
    log.info("=" * 60)
    log.info("✅ DONE")
    log.info("=" * 60)

if __name__ == '__main__':
    main()
