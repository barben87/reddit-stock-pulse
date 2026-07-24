# Stock Pulse 📊 — דופק הרשת

Real-time Reddit stock sentiment analysis + technical analysis, powered by GitHub Actions + yfinance.

**What it does:**
- ✅ Scrapes Reddit (r/stocks, r/investing, r/wallstreetbets, r/ValueInvesting) for stock mentions
- ✅ Dynamically identifies tickers (no hardcoded list)
- ✅ Fetches real-time price data, technicals (MA20/50/150/200, RSI), and fundamentals
- ✅ Calculates sector rollups (weighted by discussion volume)
- ✅ Tracks week-over-week changes (what was buzzy last week? how did it perform?)
- ✅ Runs automatically 2x daily in the cloud (no local setup required)
- ✅ Displays in a premium React dashboard

**Free to run.** Zero operational cost.

---

## 🚀 Quick Start (5 minutes)

### 1. Register Reddit API (1 minute)

1. Go to https://reddit.com/prefs/apps
2. Click "create app" or "create another app"
3. Choose `script` type
4. Name it anything (e.g., "Stock Pulse")
5. Copy:
   - **Client ID** (under the app name)
   - **Client Secret** (in the black box)

### 2. Create GitHub Repository (2 minutes)

1. Go to https://github.com/new
2. Name: `reddit-stock-pulse`
3. **Public** (required for free GitHub Actions)
4. Create repository

### 3. Upload Files to Your Repo

Clone the repo and add these files to the root:

```
reddit-stock-pulse/
├── reddit_stock_pulse.py      (main scraper)
├── requirements.txt           (dependencies)
├── .github/
│   └── workflows/
│       └── scrape.yml         (GitHub Actions schedule)
└── data/
    └── stocks.json            (data file, auto-created)
```

Copy each file from this guide into your repo:
- **reddit_stock_pulse.py** — [copy from guide above]
- **requirements.txt** — [copy from guide above]
- **.github/workflows/scrape.yml** — [copy from guide above]
- **data/stocks.json** — create with empty template:
```json
{"stocks": {}, "sectors": {}, "updated_at": "2026-01-01T00:00:00Z"}
```

### 4. Set GitHub Secrets (2 minutes)

In your repo:
1. Settings → Secrets and variables → Actions → New repository secret
2. Add these 3 secrets:

| Name | Value |
|------|-------|
| `REDDIT_CLIENT_ID` | Your Client ID from step 1 |
| `REDDIT_CLIENT_SECRET` | Your Client Secret from step 1 |
| `REDDIT_USER_AGENT` | `StockPulse/1.0 (by your_reddit_username)` |

### 5. Trigger the Scraper Manually (first time)

1. Go to Actions tab in your repo
2. Select "Scrape Reddit Stocks" workflow
3. Click "Run workflow" → "Run workflow"
4. Wait ~2 minutes

After it finishes, you'll have a fresh `data/stocks.json` with real data.

### 6. Automatic Scheduling

The workflow runs automatically:
- **6:00 AM UTC** (9:00 AM Israel time)
- **6:00 PM UTC** (9:00 PM Israel time)

You can edit the cron times in `.github/workflows/scrape.yml` if needed.

---

## 📊 Using the Frontend

### Option A: Display in GitHub Pages (Static)

1. Upload `index.html` (or `reddit_stock_pulse_v3.jsx` converted to HTML) to your repo
2. Settings → Pages → set source to main branch
3. Visit `https://yourusername.github.io/reddit-stock-pulse`

The frontend will fetch `data/stocks.json` from your repo and display it live.

### Option B: Run Locally with React

```bash
npm install react react-dom recharts lucide-react
npm start
```

Include the `reddit_stock_pulse_v3.jsx` component and have it fetch from `data/stocks.json`.

---

## 📋 Data Structure

After the scraper runs, `data/stocks.json` looks like:

```json
{
  "stocks": {
    "NVDA": {
      "price": 135.42,
      "dayChange": 2.1,
      "weekChange": 5.3,
      "monthChange": 12.8,
      "sixMonthChange": 45.2,
      "technicals": {
        "ma20": 130.5,
        "ma50": 128.3,
        "ma150": 120.1,
        "ma200": 115.2,
        "rsi": 65.4
      },
      "fundamentals": {
        "marketCap": 3300000000000,
        "pe": 62.5,
        "sector": "Semiconductors",
        "industry": "Semiconductor Equipment & Materials"
      },
      "reddit": {
        "mentions": 145,
        "bullish": 89,
        "bearish": 12,
        "neutral": 44,
        "subreddits": {
          "stocks": 56,
          "investing": 32,
          "wallstreetbets": 41,
          "ValueInvesting": 16
        }
      }
    }
    // ... more stocks
  },
  "sectors": {
    "Semiconductors": {
      "avgWeekChange": 4.8,
      "tickers": ["NVDA", "AMD", "AVGO"],
      "totalMentions": 324
    }
    // ... more sectors
  },
  "updated_at": "2026-01-10T18:05:00Z"
}
```

---

## 🔧 Troubleshooting

### "API rate limit exceeded" or "401 Unauthorized"

- Check your secrets in GitHub Settings
- Make sure `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` are correct (no extra spaces)
- Verify `REDDIT_USER_AGENT` includes your actual Reddit username

### "No data in stocks.json" after first run

1. Go to Actions → check the scraper workflow
2. Click the failed run and expand "Run scraper" step
3. Look for error messages:
   - "ModuleNotFoundError: No module named 'praw'" → check `requirements.txt` is in root
   - Reddit auth errors → check secrets
   - yfinance errors → might be rate-limited; it'll retry next run

### Workflow not running on schedule

1. Check Actions → see if the scheduled workflow is enabled
2. GitHub Actions might be disabled for your account; go to Settings → Actions and enable it
3. You can manually trigger via "Run workflow" button to test

### Want to change the schedule?

Edit `.github/workflows/scrape.yml` and change the `cron` line:

```yaml
- cron: '0 9,21 * * *'  # 9 AM and 9 PM UTC
```

(Use https://crontab.guru to test cron syntax)

---

## 📈 What Next?

- Modify `reddit_stock_pulse.py` to add more subreddits or custom filtering
- Build custom charts/exports based on `data/stocks.json`
- Use the data to backtest trading strategies
- Share the GitHub Pages dashboard publicly

---

## 🔐 Privacy & Safety

- Reddit API credentials are stored as **GitHub Secrets** (encrypted, not visible in logs)
- Data stored in your repo is what you choose to share
- The scraper only reads Reddit posts (no authentication required beyond your app credentials)
- yfinance is a community wrapper around public Yahoo Finance data

---

## 📚 Resources

- **PRAW (Reddit API):** https://praw.readthedocs.io/
- **yfinance:** https://github.com/ranaroussi/yfinance
- **GitHub Actions:** https://docs.github.com/actions
- **Cron syntax:** https://crontab.guru

---

Made with ❤️ for the Reddit stock community.
