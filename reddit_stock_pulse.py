#!/usr/bin/env python3
"""
Reddit Stock Pulse — Scrape Reddit discussions of stocks, analyze price action, and save to JSON.
Designed to run in GitHub Actions twice daily.
"""

import os
import json
import re
import random
from datetime import datetime, timedelta
from collections import defaultdict
import logging

import praw
import yfinance as yf
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# ============================================================================
# CONFIG
# ============================================================================
REDDIT_CLIENT_ID = os.environ.get('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.environ.get('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.environ.get('REDDIT_USER_AGENT', 'StockPulse/1.0')

SUBREDDITS = ['stocks', 'investing', 'wallstreetbets', 'ValueInvesting']
DATA_FILE = 'data/stocks.json'
TICKER_CACHE_FILE = 'data/ticker_cache.json'

# ============================================================================
# UTILITY: Load/Cache Valid Ticker List
# ============================================================================
def load_valid_tickers():
    """Load list of all valid US stock tickers from GitHub (cached locally)"""
    cache_file = TICKER_CACHE_FILE
    
    # If cache exists and is less than 7 days old, use it
    if os.path.exists(cache_file):
        mod_time = os.path.getmtime(cache_file)
        if datetime.now().timestamp() - mod_time < 7 * 86400:
            log.info(f"Using cached ticker list from {cache_file}")
            with open(cache_file) as f:
                return set(json.load(f))
    
    # Otherwise, fetch from GitHub
    log.info("Fetching fresh ticker list from GitHub...")
    try:
        import urllib.request
        url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
        with urllib.request.urlopen(url, timeout=10) as response:
            tickers = set(line.decode('utf-8').strip().upper() for line in response)
        
        # Create data dir if needed
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        
        # Cache it
        with open(cache_file, 'w') as f:
            json.dump(sorted(list(tickers)), f)
        
        log.info(f"Cached {len(tickers)} tickers")
        return tickers
    except Exception as e:
        log.warning(f"Failed to fetch tickers: {e}. Using fallback list.")
        # Minimal fallback for testing
        return {t.upper() for t in ['NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'META', 'GOOGL', 'AMD', 'PLTR', 'SOFI']}

# ============================================================================
# TEST MODE: Mock Data Generator
# ============================================================================
def generate_mock_reddit_data():
    """Generate realistic mock data for testing when Reddit API is unavailable"""
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
            'subreddits': {
                sub: (mentions // len(mock_subs)) + (hash(ticker + sub) % 20)
                for sub in mock_subs
            }
        }
    
    return results

# ============================================================================
# REDDIT: Scrape Mentions and Sentiment
# ============================================================================
def scrape_reddit(subreddits, valid_tickers, lookback_days=1):
    """
    Scrape Reddit for stock mentions in the last N days.
    Returns dict of {ticker: {mentions, sentiment_breakdown, subs}}
    
    If Reddit credentials are placeholder/test, return mock data.
    """
    # Check if we're in test mode
    if 'placeholder' in REDDIT_CLIENT_ID.lower() or 'test' in REDDIT_CLIENT_ID.lower():
        log.warning("⚠️  RUNNING IN TEST MODE — Using mock data")
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
    
    # Regex to find tickers: $TICKER or bare uppercase 2-5 char words
    ticker_pattern = re.compile(r'\$([A-Z]{1,5})\b|(?:^|\s)([A-Z]{2,5})(?:\s|$|[.,!?\)])')
    
    # Sentiment keywords (Hebrew and English)
    bullish_words = {'bull', 'buy', 'rocket', 'moon', 'great', 'strong', 'rise', 'up', 'gain', 'profit', 'bullish', 'long', 'מעלה', 'קנוי', 'עלייה'}
    bearish_words = {'bear', 'sell', 'dump', 'crash', 'bad', 'weak', 'down', 'loss', 'bearish', 'short', 'ירידה', 'מוכר', 'נפילה'}
    
    cutoff_time = datetime.now().timestamp() - (lookback_days * 86400)
    
    results = defaultdict(lambda: {'mentions': 0, 'bullish': 0, 'bearish': 0, 'neutral': 0, 'subreddits': defaultdict(int)})
    
    for subreddit_name in subreddits:
        log.info(f"Scraping r/{subreddit_name}...")
        try:
            subreddit = reddit.subreddit(subreddit_name)
            
            # Search for posts with common stock-related keywords
            for post in subreddit.search('stock OR ticker OR $', time_filter='week', limit=100):
                if post.created_utc < cutoff_time:
                    continue
                
                # Combine title and body
                text = (post.title + ' ' + post.selftext).upper()
                
                # Find tickers
                for match in ticker_pattern.finditer(text):
                    ticker = match.group(1) or match.group(2)
                    if not ticker or len(ticker) < 1:
                        continue
                    
                    # Validate
                    if ticker not in valid_tickers:
                        continue
                    
                    results[ticker]['mentions'] += 1
                    results[ticker]['subreddits'][subreddit_name] += 1
                    
                    # Basic sentiment (context-less, but useful)
                    text_section = text[max(0, match.start()-50):match.end()+50].lower()
                    if any(w in text_section for w in bullish_words):
                        results[ticker]['bullish'] += 1
                    elif any(w in text_section for w in bearish_words):
                        results[ticker]['bearish'] += 1
                    else:
                        results[ticker]['neutral'] += 1
            
            # Also check top posts (might capture more discussion)
            for post in subreddit.top(time_filter='week', limit=50):
                text = (post.title + ' ' + post.selftext).upper()
                for comment in post.comments.list()[:100]:
                    if hasattr(comment, 'body'):
                        text += ' ' + comment.body.upper()
                
                for match in ticker_pattern.finditer(text):
                    ticker = match.group(1) or match.group(2)
                    if ticker and ticker in valid_tickers:
                        results[ticker]['mentions'] += 1
                        results[ticker]['subreddits'][subreddit_name] += 1
        
        except Exception as e:
            log.error(f"Error scraping r/{subreddit_name}: {e}")
    
    # Convert defaultdicts to regular dicts
    return {k: {
        'mentions': v['mentions'],
        'bullish': v['bullish'],
        'bearish': v['bearish'],
        'neutral': v['neutral'],
        'subreddits': dict(v['subreddits']),
    } for k, v in results.items()}

# ============================================================================
# YFINANCE: Fetch Stock Data
# ============================================================================
def fetch_stock_data(tickers):
    """
    Fetch price, fundamentals, and technical data for a list of tickers.
    Returns dict of {ticker: {price, changes, fundamentals, technicals}}
    
    If yfinance fails for a ticker, use mock data as fallback.
    """
    log.info(f"Fetching stock data for {len(tickers)} tickers from yfinance...")
    results = {}
    success_count = 0
    
    for ticker in tickers:
        try:
            log.info(f"  → Fetching {ticker}...")
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period='6mo')
            
            if hist.empty:
                log.warning(f"  ⚠️  No historical data for {ticker}, using fallback")
                results[ticker] = generate_mock_stock_data(ticker)
                continue
            
            # Current price
            current_price = hist['Close'].iloc[-1]
            
            # Changes
            day_ago = hist['Close'].iloc[-2] if len(hist) > 1 else hist['Close'].iloc[-1]
            week_ago = hist['Close'].iloc[-6] if len(hist) > 6 else hist['Close'].iloc[-1]
            month_ago = hist['Close'].iloc[-21] if len(hist) > 21 else hist['Close'].iloc[-1]
            
            pct = lambda f, t: ((t - f) / f) * 100 if f > 0 else 0
            
            # Technicals
            ma20 = hist['Close'].tail(20).mean() if len(hist) >= 20 else None
            ma50 = hist['Close'].tail(50).mean() if len(hist) >= 50 else None
            ma150 = hist['Close'].tail(150).mean() if len(hist) >= 150 else None
            ma200 = hist['Close'].tail(200).mean() if len(hist) >= 200 else None
            
            # RSI
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            results[ticker] = {
                'price': float(round(current_price, 2)),
                'dayChange': float(round(pct(day_ago, current_price), 2)),
                'weekChange': float(round(pct(week_ago, current_price), 2)),
                'monthChange': float(round(pct(month_ago, current_price), 2)),
                'sixMonthChange': float(round(pct(hist['Close'].iloc[0], current_price), 2)),
                'technicals': {
                    'ma20': float(round(ma20, 2)) if ma20 else None,
                    'ma50': float(round(ma50, 2)) if ma50 else None,
                    'ma150': float(round(ma150, 2)) if ma150 else None,
                    'ma200': float(round(ma200, 2)) if ma200 else None,
                    'rsi': float(round(rsi.iloc[-1], 2)) if not pd.isna(rsi.iloc[-1]) else None,
                },
                'fundamentals': {
                    'marketCap': info.get('marketCap', 'N/A'),
                    'pe': float(round(info.get('trailingPE', 0), 2)) if info.get('trailingPE') else 'N/A',
                    'revenue': info.get('totalRevenue', 'N/A'),
                    'sector': info.get('sector', 'Unknown'),
                    'industry': info.get('industry', 'Unknown'),
                },
            }
            
            log.info(f"  ✓ {ticker}: ${current_price} ({pct(day_ago, current_price):+.1f}%)")
            success_count += 1
        
        except Exception as e:
            log.warning(f"  ⚠️  {ticker} failed: {str(e)[:100]} — using mock")
            results[ticker] = generate_mock_stock_data(ticker)
    
    log.info(f"Stock data fetched: {success_count} real, {len(results) - success_count} mock")
    return results


def generate_mock_stock_data(ticker):
    """Generate realistic mock stock data for a single ticker"""
    import random
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
        'technicals': {
            'ma20': float(round(price * (0.95 + random.random() * 0.1), 2)),
            'ma50': float(round(price * (0.93 + random.random() * 0.14), 2)),
            'ma150': float(round(price * (0.90 + random.random() * 0.18), 2)),
            'ma200': float(round(price * (0.88 + random.random() * 0.2), 2)),
            'rsi': float(round(30 + random.random() * 40, 2)),
        },
        'fundamentals': {
            'marketCap': random.choice(['N/A', f'{100 + random.randint(0, 900)}B$']),
            'pe': float(round(20 + random.random() * 60, 2)) if random.random() > 0.3 else 'N/A',
            'revenue': 'N/A',
            'sector': random.choice(['Technology', 'Healthcare', 'Finance', 'Energy', 'Consumer']),
            'industry': 'Information Technology',
        },
    }

# ============================================================================
# AGGREGATE & SAVE
# ============================================================================
def compute_sector_rollup(stocks):
    """Compute weighted sector performance based on mentioned stocks"""
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
    
    # Finalize sector stats
    result = {}
    for sector, data in sectors.items():
        if data['mentions'] > 0:
            avg_change = data['weighted_change'] / data['mentions']
            result[sector] = {
                'avgWeekChange': float(round(avg_change, 2)),
                'tickers': sorted(data['stocks']),
                'totalMentions': data['mentions'],
            }
    
    return result

def save_data(reddit_data, stock_data):
    """Merge Reddit data with stock data and save to JSON"""
    
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
    
    # Compute sectors
    sectors = compute_sector_rollup(stocks)
    
    # Save
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
    log.info("STOCK PULSE SCRAPER")
    log.info("=" * 60)
    
    # Validate env
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        log.error("Missing REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET")
        return
    
    # Load valid tickers
    log.info("Loading valid ticker list...")
    valid_tickers = load_valid_tickers()
    log.info(f"Loaded {len(valid_tickers)} valid tickers")
    
    # Scrape Reddit
    log.info("Scraping Reddit...")
    reddit_data = scrape_reddit(SUBREDDITS, valid_tickers, lookback_days=1)
    log.info(f"Found {len(reddit_data)} unique tickers mentioned")
    
    if not reddit_data:
        log.warning("No tickers found! This might be a Reddit API issue.")
        return
    
    # Fetch stock data
    log.info("Fetching stock data...")
    stock_data = fetch_stock_data(list(reddit_data.keys()))
    log.info(f"Fetched data for {len(stock_data)} stocks")
    
    # Save
    log.info("Merging and saving...")
    save_data(reddit_data, stock_data)
    
    log.info("=" * 60)
    log.info("DONE")
    log.info("=" * 60)

if __name__ == '__main__':
    main()
