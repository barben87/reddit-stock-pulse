# Stock Pulse — מדריך הקמה (עברית)

## סיכום קצר

אתה בונה סקריפט Python שרץ **אוטומטית ב-GitHub** (חינם) פעמיים ביום, סורק את Reddit, מוצא אזכורי מניות, מושך מחירים אמיתיים מ-yfinance, מחשב טכנים וסקטורים, ושומר הכל לקובץ JSON. אחרי זה, דשבורד React (שהכנו) קורא את הקובץ הזה ומציג את הנתונים בצורה יפה.

**עלות:** 0₪. לגמרי חינם.

---

## שלב 1: הרשמה ל-Reddit API (5 דקות)

1. כנס ל- https://reddit.com/prefs/apps (צריך להיות logged in)
2. לחץ על "create an application" או "create another app"
3. בחר סוג: **script**
4. שם: כתוב משהו כמו `Stock Pulse` או `Reddit Stock Scraper`
5. קבל את ה-permissions (default זה בסדר)
6. לחץ "create app"

**השמור:**
בחלון שנפתח תראה:
- `personal use script` — זה ה-**Client ID**
- `secret` — זה ה-**Client Secret** (בתוך הכיתה השחורה)

כתוב אותם איפהשהוא בטמפורר (בהודעה / Notepad).

---

## שלב 2: הקמת Repo ב-GitHub (2 דקות)

1. כנס ל-https://github.com/new
2. שם repo: `reddit-stock-pulse`
3. **חשוב:** בחר **Public** (ההשקעה: GitHub Actions בחינם רק לריפו ציבוריים)
4. לא בחר README או gitignore
5. לחץ "Create repository"

אתה תקבל ריפו ריק שמחכה לקבצים.

---

## שלב 3: העלאת קבצים לריפו

**שם הקבצים וניתיביהם — חשוב לדייק בזה:**

### קובץ 1: `reddit_stock_pulse.py`
בשורש הריפו (לא בתת-תיקייה). [קובץ זה מספק כמו-מלוא Python].

### קובץ 2: `requirements.txt`
בשורש. תוכן:
```
praw==7.7.0
yfinance==0.2.32
pandas==2.1.4
```

### קובץ 3: `.github/workflows/scrape.yml`
**בדיוק בנתיב הזה** — .github/workflows/scrape.yml (שים לב: נקודה בהתחלה). [קובץ YAML שמוגדר למטה].

### קובץ 4: `data/stocks.json`
בתיקייה `data` (צור אותה אם לא קיימת). תוכן:
```json
{"stocks": {}, "sectors": {}, "updated_at": "2026-01-01T00:00:00Z"}
```

**איך להעלות:**
- **אפשרות א:** GitHub web interface — לחץ "Add file" → "Create new file" / "Upload files" וחזור על כל קובץ.
- **אפשרות ב:** Clone לוקלי (במידה וכבר יש לך Git):
  ```bash
  git clone https://github.com/YOUR-USERNAME/reddit-stock-pulse.git
  cd reddit-stock-pulse
  # העתק את הקבצים לתיקייה זו
  git add .
  git commit -m "Initial commit"
  git push
  ```

---

## שלב 4: הגדרת Secrets ב-GitHub (3 דקות)

אלה מידע שרוצים להסתיר (Client ID/Secret) אבל GitHub Actions צריך להשתמש בהם.

1. בדף הריפו, לחץ **Settings** (בחלק העליון)
2. בצד שמאל, בחר **Secrets and variables** → **Actions**
3. לחץ **New repository secret**
4. צור את 3 ה-secrets הבאים:

| שם | ערך |
|----|----|
| `REDDIT_CLIENT_ID` | Client ID שקיבלת בשלב 1 |
| `REDDIT_CLIENT_SECRET` | Client Secret שקיבלת בשלב 1 |
| `REDDIT_USER_AGENT` | `StockPulse/1.0 (by YOUR_REDDIT_USERNAME)` — החלף YOUR_REDDIT_USERNAME עם שם ה-Reddit שלך |

---

## שלב 5: הפעלה ידנית בפעם הראשונה (2 דקות)

1. בדף הריפו, לחץ **Actions**
2. בצד שמאל תראה "Scrape Reddit Stocks" — לחץ עליו
3. לחץ **Run workflow** → **Run workflow**
4. המתן ~1-2 דקות

בזמן זה:
- GitHub מתחיל מכונה קטנה
- מריץ את `reddit_stock_pulse.py`
- סורק Reddit
- מושך מחירים מ-yfinance
- שומר את הכל ל-`data/stocks.json`
- מעלה את הקובץ חזרה לריפו

אחרי שמסתיים:
1. בדוק ש-`data/stocks.json` אינו ריק — לחץ עליו בדף הריפו ותראה את הנתונים.

אם יש שגיאה:
- לחץ על ה-workflow run שכשל
- בחר "Scrape Reddit Stocks" בצד
- לחץ על "Run scraper" וגלול — תראה הודעות שגיאה

---

## שלב 6: תזמון אוטומטי

כרגע, ה-workflow מוגדר להיות כל:
- **6:00 בבוקר UTC** = 09:00 בישראל
- **18:00 UTC** = 21:00 בישראל

זה אומר: פעמיים ביום, GitHub מתעורר באוטומט, מריץ את הסקריפט, וגדרונים את הנתונים החדשים לק קובץ `data/stocks.json`.

אם אתה רוצה לשנות את הזמנים:
1. בדף הריפו, לחץ על `code` / `<>` (דף הקוד)
2. פתח `.github/workflows/scrape.yml`
3. בחלק `schedule:` (בתחילת הקובץ) תראה `cron:` שדברים בסגנון `'0 6,18 * * *'`
4. לחץ עט (edit) וגנוב את הזמנים:
   - `0 9,21` = 09:00 ו-21:00 UTC
   - `0 7,19` = 07:00 ו-19:00 UTC
   - (בדוק https://crontab.guru אם אתה לא בטוח)
5. Commit

---

## שלב 7: התחברות לדשבורד (React)

יש לך שתי אפשרויות:

### אפשרות א: GitHub Pages (אתר סטטי)

1. העלה את `reddit_stock_pulse_v3.jsx` אל הריפו (או המור אותו ל-HTML)
2. Settings → Pages → set source to `main` branch
3. אחרי דקה, תקבל קישור כמו `https://YOUR-USERNAME.github.io/reddit-stock-pulse/`
4. פתח את הקישור בדפדפן

הדשבורד **יקרא ישירות מ-`data/stocks.json`** בריפו.

### אפשרות ב: מחשב שלך (בפיתוח)

בפיתוח מקומי עם Vite:
```bash
npm create vite@latest my-app -- --template react
cd my-app
npm install
npm install react-dom recharts lucide-react
# העתק את reddit_stock_pulse_v3.jsx ל-src/App.jsx
npm run dev
```

אחרי זה:
1. בקובץ `reddit_stock_pulse_v3.jsx` בחלק ה-`fetch` בתחילת ה-component:
```javascript
useEffect(() => {
  fetch('/data/stocks.json') // או URL לhttps://raw.githubusercontent.com/YOUR/reddit-stock-pulse/main/data/stocks.json
    .then(r => r.json())
    .then(data => setStocks(data.stocks))
    .catch(err => console.error(err))
}, [])
```
2. Run `npm run dev`
3. פתח localhost ורואה את הדשבורד עם נתונים אמיתיים.

---

## שלב 8: צפיה בנתונים

שלוש דרכים:

1. **ישירות בGitHub:** בדף הריפו, לחץ על `data/stocks.json` ותראה את ה-JSON
2. **בדפדפן:** עבור ל-GitHub Pages (אם הוגדר) ותראה את הדשבורד
3. **בטרמינל (אם Clone לוקלי):**
   ```bash
   cat data/stocks.json | python -m json.tool
   ```

---

## מה עוד?

### הוספת סאברדיטים נוספים
בקובץ `reddit_stock_pulse.py`, שורה `SUBREDDITS = [...]`:
```python
SUBREDDITS = ['stocks', 'investing', 'wallstreetbets', 'ValueInvesting', 'securityanalysis', 'Stocks4Beginners']
```

### שינוי זמן הריצה
בקובץ `.github/workflows/scrape.yml`, שנה את ה-cron.

### ניטור שגיאות
GitHub Actions שלך שומר logs. בכל run נושך Actions:
- צבע ירוק = הצליח
- צבע אדום = שגיאה → לחץ להסתכל ב-logs

---

## בעיות נפוצות

### "401 Unauthorized" או "Authentication failed"
**סיבה:** Secrets לא נכונים או חסרים.
**פתרון:** בדוק ש-REDDIT_CLIENT_ID וREDDIT_CLIENT_SECRET בדיוק כמו שקיבלת מ-Reddit (ללא רווחים או קווי-טקסט נוסף).

### "No module named 'praw'"
**סיבה:** requirements.txt לא בשורש הריפו.
**פתרון:** וודא שה-קובץ `requirements.txt` בדיוק בשורש (לא בתת-תיקייה).

### "Workflow is running but not committing changes"
**סיבה:** permissions בGitHub Actions.
**פתרון:** בדוק ש-Settings → Actions → General → Workflow permissions מוגדר ל-"Read and write".

### "No data found" או "Empty stocks.json"
**סיבה:** אולי Reddit API לא החזיר תוצאות או יש בעיה ב-yfinance.
**פתרון:** חכה כמה שעות והנסה שוב. לפעמים יש congestion זמני.

---

## 🎉 מה קרה?

אתה כעת בעל:
✅ סקריפט Python שרץ בענן (GitHub Actions)
✅ Scraper של Reddit מדינמי (ללא hardcoded tickers)
✅ Fetcher של נתוני Stock אמיתיים (מחירים, טכנים, סקטורים)
✅ Dashboard React יפה שמציג הכל
✅ זרימת נתונים רציפה (כל 12 שעות)

הכל חינם, בלי שום מחשב רץ בבית שלך.

---

## שאלות?

- Reddit API issues? https://praw.readthedocs.io/
- GitHub Actions? https://docs.github.com/actions
- yfinance issues? https://github.com/ranaroussi/yfinance/issues
