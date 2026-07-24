import React, { useState, useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine,
} from "recharts";
import {
  TrendingUp, TrendingDown, Flame, ChevronDown, MessageSquare,
  Target, ShieldAlert, Activity, Gauge, Building2, History, Minus, Layers,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/* Tokens — premium pass                                               */
/* ------------------------------------------------------------------ */
const C = {
  void: "#07090D",
  panel: "#12161F",
  panelGradTop: "#161B26",
  panelGradBottom: "#0F1219",
  panelRaised: "#1B2130",
  line: "rgba(255,255,255,0.07)",
  lineStrong: "rgba(255,255,255,0.12)",
  textPrimary: "#F1F3F7",
  textMuted: "#8993A8",
  textFaint: "#5B6478",
  gain: "#3FE0A0",
  gainDim: "rgba(63,224,160,0.12)",
  loss: "#FF6B6B",
  lossDim: "rgba(255,107,107,0.12)",
  gold: "#F0B429",
  goldDim: "rgba(240,180,41,0.12)",
  subStocks: "#6E9BFF",
  subInvesting: "#B79CFF",
  subWsb: "#FF7D52",
  subValue: "#2FE0C9",
};

const SUB_META = {
  stocks: { label: "r/stocks", color: C.subStocks },
  investing: { label: "r/investing", color: C.subInvesting },
  wallstreetbets: { label: "r/wallstreetbets", color: C.subWsb },
  ValueInvesting: { label: "r/ValueInvesting", color: C.subValue },
};

const cardShadow = "0 12px 30px -14px rgba(0,0,0,0.55), 0 2px 8px -2px rgba(0,0,0,0.4)";
const cardBg = `linear-gradient(165deg, ${C.panelGradTop}, ${C.panelGradBottom})`;

/* ------------------------------------------------------------------ */
/* Seeded mock-data generation                                         */
/* ------------------------------------------------------------------ */
function hashStr(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) { h = (h << 5) - h + s.charCodeAt(i); h |= 0; }
  return Math.abs(h);
}
function mulberry32(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function genSeries(rng, base, drift, vol, n = 200) {
  const arr = [base];
  for (let i = 1; i < n; i++) {
    const shock = (rng() - 0.5) * 2 * vol;
    let next = arr[i - 1] * (1 + drift / n + shock);
    if (next < 1) next = 1;
    arr.push(next);
  }
  return arr;
}
function sma(arr, window) {
  return arr.map((_, i) => {
    if (i < window - 1) return null;
    let sum = 0;
    for (let j = i - window + 1; j <= i; j++) sum += arr[j];
    return sum / window;
  });
}
function genBuzz(rng, total) {
  const arr = [];
  for (let i = 0; i < 24; i++) arr.push(Math.max(1, Math.round(rng() * (total / 7))));
  return arr;
}

const BASE = [
  { t: "NVDA", name: "NVIDIA", blurb: "מעצבת שבבי הגרפיקה וה-AI המובילים בעולם, עם שליטה כמעט מוחלטת בשוק שבבי האימון לבינה מלאכותית.", sector: "מוליכים למחצה", price: 135, pe: "62", cap: "3.3T$", rev: 78 },
  { t: "TSLA", name: "Tesla", blurb: "יצרנית רכב חשמלי ואגירת אנרגיה, עם שאיפות ברובוטיקה ונהיגה אוטונומית.", sector: "רכב חשמלי", price: 245, pe: "68", cap: "780B$", rev: 6 },
  { t: "PLTR", name: "Palantir", blurb: "פלטפורמת ניתוח נתונים ובינה מלאכותית ללקוחות ממשלתיים וארגוניים גדולים.", sector: "תוכנה / AI", price: 28, pe: "190", cap: "62B$", rev: 27 },
  { t: "AMD", name: "AMD", blurb: "יצרנית מעבדים ושבבי GPU, המתחרה המרכזית של אינטל ו-NVIDIA.", sector: "מוליכים למחצה", price: 152, pe: "45", cap: "245B$", rev: 14 },
  { t: "SOFI", name: "SoFi", blurb: "בנק דיגיטלי ופלטפורמת שירותים פיננסיים אונליין המיועדת בעיקר לדור הצעיר.", sector: "פינטק", price: 9.2, pe: "-", cap: "9.8B$", rev: 33 },
  { t: "SMCI", name: "Super Micro", blurb: "יצרנית שרתים ותשתיות מחשוב לענן ולעומסי עבודה של בינה מלאכותית.", sector: "חומרה", price: 42, pe: "21", cap: "24B$", rev: 40 },
  { t: "AAPL", name: "Apple", blurb: "מובייל, מחשוב אישי ושירותים דיגיטליים - אחת החברות הגדולות בעולם.", sector: "טכנולוגיה", price: 212, pe: "31", cap: "3.2T$", rev: 5 },
  { t: "META", name: "Meta Platforms", blurb: "פייסבוק, אינסטגרם ו-WhatsApp, עם השקעה כבדה ב-AI ובמציאות מדומה.", sector: "מדיה חברתית", price: 495, pe: "27", cap: "1.25T$", rev: 19 },
  { t: "COIN", name: "Coinbase", blurb: "בורסת המטבעות הדיגיטליים הגדולה בארה״ב.", sector: "קריפטו", price: 245, pe: "38", cap: "60B$", rev: 55 },
  { t: "RIVN", name: "Rivian", blurb: "יצרנית רכבי שטח ומשאיות מסחריות חשמליות.", sector: "רכב חשמלי", price: 13, pe: "-", cap: "13B$", rev: 12 },
  { t: "MSTR", name: "MicroStrategy", blurb: "חברת תוכנה שהפכה לאחזקת הביטקוין הגדולה בעולם בקרב חברות ציבוריות.", sector: "תוכנה / קריפטו", price: 380, pe: "-", cap: "85B$", rev: 3 },
  { t: "GME", name: "GameStop", blurb: "רשת חנויות משחקי וידאו, סמל תנועת המניות ה'משופצות' של קהילת WSB.", sector: "קמעונאות", price: 24, pe: "95", cap: "10.8B$", rev: -12 },
  { t: "AVGO", name: "Broadcom", blurb: "שבבי רשת ותקשורת, לצד תוכנת תשתית ארגונית.", sector: "מוליכים למחצה", price: 165, pe: "33", cap: "780B$", rev: 22 },
  { t: "MSFT", name: "Microsoft", blurb: "ענן Azure, מערכת ההפעלה Windows ו-Office, עם השקעה כבדה ב-OpenAI.", sector: "טכנולוגיה", price: 465, pe: "36", cap: "3.4T$", rev: 15 },
  { t: "AMZN", name: "Amazon", blurb: "מסחר אלקטרוני, ענן AWS ופרסום דיגיטלי.", sector: "מסחר אלקטרוני", price: 205, pe: "34", cap: "2.1T$", rev: 11 },
  { t: "GOOGL", name: "Alphabet", blurb: "מנוע החיפוש Google, יוטיוב וענן Google Cloud.", sector: "טכנולוגיה", price: 178, pe: "22", cap: "2.2T$", rev: 13 },
  { t: "NFLX", name: "Netflix", blurb: "שירות הסטרימינג המוביל בעולם.", sector: "מדיה", price: 680, pe: "40", cap: "290B$", rev: 15 },
  { t: "INTC", name: "Intel", blurb: "יצרנית מעבדים ומפעלי ייצור שבבים, בעיצומו של תהליך הבראה.", sector: "מוליכים למחצה", price: 22, pe: "-", cap: "95B$", rev: -8 },
  { t: "MARA", name: "Marathon Digital", blurb: "חברת כרייה של ביטקוין בהיקף תעשייתי.", sector: "קריפטו", price: 15, pe: "-", cap: "4.5B$", rev: 45 },
  { t: "HOOD", name: "Robinhood", blurb: "אפליקציית מסחר ומניות ללקוחות פרטיים.", sector: "פינטק", price: 38, pe: "42", cap: "34B$", rev: 30 },
];

function buildStock(base, i) {
  const rng = mulberry32(hashStr(base.t) + i * 7919);
  const drift = (rng() - 0.42) * 0.55;
  const vol = 0.014 + rng() * 0.022;
  const series = genSeries(rng, base.price * 0.85, drift, vol, 200);
  const ma20 = sma(series, 20), ma50 = sma(series, 50), ma150 = sma(series, 150), ma200 = sma(series, 200);
  const last = series[series.length - 1];
  const pct = (from, to) => ((to - from) / from) * 100;
  const dayChange = pct(series[series.length - 2], last);
  const weekChange = pct(series[series.length - 6], last);
  const monthChange = pct(series[series.length - 22], last);
  const sixMoChange = pct(series[0], last);

  const totalMentions = 35 + Math.round(rng() * 640);
  const w = { stocks: rng(), investing: rng(), wallstreetbets: rng(), ValueInvesting: rng() };
  const wsum = w.stocks + w.investing + w.wallstreetbets + w.ValueInvesting;
  const bySub = Object.fromEntries(Object.entries(w).map(([k, v]) => [k, Math.max(1, Math.round((totalMentions * v) / wsum))]));

  // independent draw so last week's buzz ranking isn't just today's ranking
  const rngWeek = mulberry32(hashStr(base.t + "w") + i * 104729);
  const lastWeekMentions = 25 + Math.round(rngWeek() * 520);
  const priceLastWeek = series[series.length - 6];

  const bullish = Math.round(28 + rng() * 58);
  const rsi = Math.round(24 + rng() * 56);
  const buzz = genBuzz(rng, totalMentions);
  const ma150Last = ma150[ma150.length - 1];
  const trendUp = ma150Last ? last > ma150Last : last > ma50[ma50.length - 1];
  const momentumUp = ma20[ma20.length - 1] > ma50[ma50.length - 1];

  const support = last * (0.9 - rng() * 0.05);
  const target = last * (1.1 + rng() * 0.14);
  const stop = support * (0.95 - rng() * 0.03);

  return {
    ...base, series, ma20, ma50, ma150, ma200, price: last,
    dayChange, weekChange, monthChange, sixMoChange,
    totalMentions, bySub, bullish, rsi, buzz, trendUp, momentumUp,
    support, target, stop, lastWeekMentions, priceLastWeek,
  };
}

/* ------------------------------------------------------------------ */
/* Small helpers                                                       */
/* ------------------------------------------------------------------ */
const fmt$ = (n) => `$${n.toFixed(n < 20 ? 2 : 1)}`;
const fmtPct = (n) => `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;

function ChangeTag({ value, label }) {
  const up = value >= 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3, minWidth: 56 }}>
      <span style={{ fontSize: 10, color: C.textFaint, letterSpacing: 0.3 }}>{label}</span>
      <span style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, color: up ? C.gain : C.loss,
        fontVariantNumeric: "tabular-nums",
      }}>
        {fmtPct(value)}
      </span>
    </div>
  );
}

function MiniSpark({ values, color, w = 90, h = 28, fill = false }) {
  const max = Math.max(...values), min = Math.min(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return [x, y];
  });
  const line = pts.map((p) => p.join(",")).join(" ");
  const area = `0,${h} ${line} ${w},${h}`;
  const gid = `g-${color.replace("#", "")}`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      {fill && (
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.35" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
      )}
      {fill && <polygon points={area} fill={`url(#${gid})`} />}
      <polyline points={line} fill="none" stroke={color} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SubDots({ bySub }) {
  return (
    <div style={{ display: "flex", gap: 9, flexWrap: "wrap" }}>
      {Object.entries(bySub).map(([k, v]) => (
        <div key={k} style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 6, height: 6, borderRadius: 99, background: SUB_META[k].color, display: "inline-block", boxShadow: `0 0 6px ${SUB_META[k].color}` }} />
          <span style={{ fontSize: 11, color: C.textMuted, fontFamily: "'JetBrains Mono', monospace" }}>{v}</span>
        </div>
      ))}
    </div>
  );
}

function SectionEyebrow({ children }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
      <span style={{ width: 3, height: 14, borderRadius: 2, background: `linear-gradient(180deg, ${C.gold}, transparent)` }} />
      <span style={{ fontSize: 12.5, color: C.textMuted, fontWeight: 600, letterSpacing: 0.2 }}>{children}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Detail panel (tabs)                                                  */
/* ------------------------------------------------------------------ */
function StockDetail({ s }) {
  const [tab, setTab] = useState("overview");
  const [range, setRange] = useState("1M");
  const rangeN = { "1W": 14, "1M": 30, "6M": 180 }[range];
  const chartData = s.series.slice(-rangeN).map((p, i) => {
    const idx = s.series.length - rangeN + i;
    return { i, price: p, ma50: s.ma50[idx], ma150: s.ma150[idx] };
  });

  const tabs = [
    { id: "overview", label: "סקירה", icon: Building2 },
    { id: "fundamentals", label: "פנדמנטלי", icon: Gauge },
    { id: "technical", label: "טכני", icon: Activity },
    { id: "chart", label: "גרף", icon: TrendingUp },
    { id: "levels", label: "כניסה / יציאה", icon: Target },
  ];

  return (
    <div style={{ borderTop: `1px solid ${C.line}`, padding: "16px 4px 6px" }}>
      <div style={{ display: "flex", gap: 6, marginBottom: 14, flexWrap: "wrap" }}>
        {tabs.map((tb) => (
          <button key={tb.id} onClick={() => setTab(tb.id)}
            style={{
              display: "flex", alignItems: "center", gap: 6, padding: "6px 12px", borderRadius: 8,
              border: `1px solid ${tab === tb.id ? C.gold : C.line}`,
              background: tab === tb.id ? C.goldDim : "transparent",
              color: tab === tb.id ? C.gold : C.textMuted, fontSize: 12.5, cursor: "pointer",
              transition: "all .15s",
            }}>
            <tb.icon size={13} /> {tb.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div>
          <p style={{ fontSize: 13.5, lineHeight: 1.7, color: C.textPrimary, margin: "0 0 10px" }}>{s.blurb}</p>
          <p style={{ fontSize: 12, color: C.textMuted, margin: 0 }}>סקטור: {s.sector}</p>
        </div>
      )}

      {tab === "fundamentals" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
          {[
            ["שווי שוק", s.cap], ["מכפיל רווח (P/E)", s.pe],
            ["צמיחת הכנסות שנתית", `${s.rev >= 0 ? "+" : ""}${s.rev}%`],
            ["מגמת רווחיות", s.rev >= 15 ? "צמיחה חזקה" : s.rev >= 0 ? "צמיחה מתונה" : "התכווצות הכנסות"],
          ].map(([k, v]) => (
            <div key={k} style={{ background: C.panelRaised, borderRadius: 10, padding: "10px 12px", border: `1px solid ${C.line}` }}>
              <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 4 }}>{k}</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 15, fontWeight: 700 }}>{v}</div>
            </div>
          ))}
        </div>
      )}

      {tab === "technical" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
          {[
            ["ממוצע נע 20", s.ma20[s.ma20.length - 1]], ["ממוצע נע 50", s.ma50[s.ma50.length - 1]],
            ["ממוצע נע 150", s.ma150[s.ma150.length - 1]], ["ממוצע נע 200", s.ma200[s.ma200.length - 1]],
          ].map(([k, v]) => (
            <div key={k} style={{ background: C.panelRaised, borderRadius: 10, padding: "10px 12px", border: `1px solid ${C.line}` }}>
              <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 4 }}>{k}</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 15, fontWeight: 700 }}>
                {v ? fmt$(v) : "אין מספיק היסטוריה"}
              </div>
            </div>
          ))}
          <div style={{ background: C.panelRaised, borderRadius: 10, padding: "10px 12px", border: `1px solid ${C.line}` }}>
            <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 4 }}>RSI (14)</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 15, fontWeight: 700, color: s.rsi > 70 ? C.loss : s.rsi < 30 ? C.gain : C.textPrimary }}>
              {s.rsi} {s.rsi > 70 ? "(קניית יתר)" : s.rsi < 30 ? "(מכירת יתר)" : "(נייטרלי)"}
            </div>
          </div>
          <div style={{ background: C.panelRaised, borderRadius: 10, padding: "10px 12px", border: `1px solid ${C.line}` }}>
            <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 4 }}>מגמה מול MA150</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 15, fontWeight: 700, color: s.trendUp ? C.gain : C.loss }}>
              {s.trendUp ? "מעל הממוצע — מגמה עולה" : "מתחת לממוצע — מגמה יורדת"}
            </div>
          </div>
          <div style={{ background: C.panelRaised, borderRadius: 10, padding: "10px 12px", gridColumn: "1 / -1", border: `1px solid ${C.line}` }}>
            <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 4 }}>מומנטום קצר מול ארוך (MA20 מול MA50)</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 15, fontWeight: 700, color: s.momentumUp ? C.gain : C.loss }}>
              {s.momentumUp ? "מומנטום חיובי" : "מומנטום שלילי"}
            </div>
          </div>
        </div>
      )}

      {tab === "chart" && (
        <div>
          <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
            {["1W", "1M", "6M"].map((r) => (
              <button key={r} onClick={() => setRange(r)}
                style={{
                  padding: "4px 10px", borderRadius: 6, fontSize: 11.5, cursor: "pointer",
                  border: `1px solid ${range === r ? C.gold : C.line}`,
                  background: range === r ? C.goldDim : "transparent",
                  color: range === r ? C.gold : C.textMuted,
                }}>{r}</button>
            ))}
          </div>
          <div style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 6, right: 6, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={C.line} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="i" hide />
                <YAxis domain={["auto", "auto"]} tick={{ fill: C.textMuted, fontSize: 10 }} width={44} />
                <Tooltip
                  contentStyle={{ background: C.panelRaised, border: `1px solid ${C.lineStrong}`, borderRadius: 8, fontSize: 12 }}
                  labelFormatter={() => ""} formatter={(v, name) => [fmt$(v), name === "price" ? "מחיר" : name.toUpperCase()]}
                />
                <ReferenceLine y={s.support} stroke={C.gain} strokeDasharray="4 4" />
                <ReferenceLine y={s.target} stroke={C.gold} strokeDasharray="4 4" />
                <Line type="monotone" dataKey="price" stroke={C.textPrimary} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="ma50" stroke={C.subStocks} strokeWidth={1.3} dot={false} />
                <Line type="monotone" dataKey="ma150" stroke={C.subWsb} strokeWidth={1.3} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: "flex", gap: 14, marginTop: 8, flexWrap: "wrap", fontSize: 11, color: C.textMuted }}>
            <span><span style={{ color: C.textPrimary }}>―</span> מחיר</span>
            <span><span style={{ color: C.subStocks }}>―</span> MA50</span>
            <span><span style={{ color: C.subWsb }}>―</span> MA150</span>
            <span><span style={{ color: C.gain }}>┈</span> תמיכה</span>
            <span><span style={{ color: C.gold }}>┈</span> יעד</span>
          </div>
        </div>
      )}

      {tab === "levels" && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 10 }}>
            <div style={{ background: C.gainDim, border: `1px solid ${C.gain}`, borderRadius: 10, padding: "10px 12px" }}>
              <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 4 }}>אזור כניסה (תמיכה)</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 15, fontWeight: 700, color: C.gain }}>{fmt$(s.support)}</div>
            </div>
            <div style={{ background: C.goldDim, border: `1px solid ${C.gold}`, borderRadius: 10, padding: "10px 12px" }}>
              <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 4 }}>יעד יציאה</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 15, fontWeight: 700, color: C.gold }}>{fmt$(s.target)}</div>
            </div>
            <div style={{ background: C.lossDim, border: `1px solid ${C.loss}`, borderRadius: 10, padding: "10px 12px" }}>
              <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 4 }}>סטופ-לוס</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 15, fontWeight: 700, color: C.loss }}>{fmt$(s.stop)}</div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "flex-start", background: C.panelRaised, borderRadius: 10, padding: "10px 12px", border: `1px solid ${C.line}` }}>
            <ShieldAlert size={15} color={C.textMuted} style={{ marginTop: 2, flexShrink: 0 }} />
            <p style={{ fontSize: 11.5, color: C.textMuted, lineHeight: 1.6, margin: 0 }}>
              הרמות מבוססות על תמיכה/התנגדות טכניות בלבד (נגזרות מהגרף וממוצעים נעים) ואינן המלצת השקעה. יש להצליב עם ניתוח עצמאי.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Card                                                                 */
/* ------------------------------------------------------------------ */
function StockCard({ s, expanded, onToggle }) {
  const up = s.dayChange >= 0;
  return (
    <div style={{
      background: cardBg, border: `1px solid ${expanded ? C.lineStrong : C.line}`, borderRadius: 16,
      overflow: "hidden", boxShadow: cardShadow, transition: "border-color .2s",
    }}>
      <button onClick={onToggle} style={{ width: "100%", textAlign: "right", background: "transparent", border: "none", cursor: "pointer", padding: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 5, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 800, fontSize: 15.5, color: C.textPrimary, letterSpacing: 0.3 }}>{s.t}</span>
              <span style={{ fontSize: 12, color: C.textMuted }}>{s.name}</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, color: C.textMuted, fontSize: 11.5 }}>
              <MessageSquare size={12} /> {s.totalMentions} אזכורים היום
            </div>
            <SubDots bySub={s.bySub} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6, flexShrink: 0 }}>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 800, fontSize: 17 }}>{fmt$(s.price)}</span>
            <div style={{
              display: "flex", alignItems: "center", gap: 4, color: up ? C.gain : C.loss, fontSize: 13,
              fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, background: up ? C.gainDim : C.lossDim,
              padding: "2px 8px", borderRadius: 999,
            }}>
              {up ? <TrendingUp size={13} /> : <TrendingDown size={13} />} {fmtPct(s.dayChange)}
            </div>
            <MiniSpark values={s.series.slice(-30)} color={up ? C.gain : C.loss} fill />
          </div>
        </div>

        <div style={{ display: "flex", gap: 16, marginTop: 14, paddingTop: 12, borderTop: `1px solid ${C.line}`, justifyContent: "space-between" }}>
          <ChangeTag value={s.dayChange} label="יום" />
          <ChangeTag value={s.weekChange} label="שבוע" />
          <ChangeTag value={s.monthChange} label="חודש" />
          <ChangeTag value={s.sixMoChange} label="חצי שנה" />
          <ChevronDown size={16} color={C.textMuted} style={{ transform: expanded ? "rotate(180deg)" : "none", transition: "transform .2s", alignSelf: "center" }} />
        </div>
      </button>
      {expanded && <div style={{ padding: "0 16px 16px" }}><StockDetail s={s} /></div>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Pulse rail (signature element)                                       */
/* ------------------------------------------------------------------ */
function PulseRail({ stocks, onPick }) {
  const top5 = [...stocks].sort((a, b) => b.totalMentions - a.totalMentions).slice(0, 5);
  const max = Math.max(...top5.map((s) => s.totalMentions));
  return (
    <div style={{ position: "relative" }}>
      <div style={{
        position: "absolute", inset: "-30px -10px auto -10px", height: 160,
        background: `radial-gradient(ellipse at 30% 0%, ${C.goldDim}, transparent 70%)`, pointerEvents: "none",
      }} />
      <div style={{ display: "flex", gap: 16, alignItems: "flex-end", padding: "18px 4px 4px", overflowX: "auto", position: "relative" }}>
        {top5.map((s, idx) => {
          const h = 34 + (s.totalMentions / max) * 100;
          return (
            <button key={s.t} onClick={() => onPick(s.t)}
              style={{ background: "transparent", border: "none", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", gap: 9, flexShrink: 0, width: 86 }}>
              <div style={{ display: "flex", alignItems: "flex-end", gap: 2 }}>
                {idx === 0 && <Flame size={14} color={C.gold} style={{ marginBottom: 4, filter: `drop-shadow(0 0 4px ${C.gold})` }} />}
                <div style={{
                  width: 32, height: h, borderRadius: "8px 8px 4px 4px",
                  background: `linear-gradient(180deg, ${C.gold}, rgba(240,180,41,0.1))`,
                  boxShadow: idx === 0 ? `0 0 16px ${C.goldDim}` : "none",
                }} />
              </div>
              <MiniSpark values={s.buzz} color={C.gold} w={72} h={16} />
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 800, fontSize: 13.5 }}>{s.t}</div>
              <div style={{ fontSize: 10.5, color: C.textMuted }}>{s.totalMentions} אזכורים</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Movers list                                                          */
/* ------------------------------------------------------------------ */
function MoversColumn({ title, list, color, icon: Icon }) {
  return (
    <div style={{ background: cardBg, border: `1px solid ${C.line}`, borderRadius: 16, padding: 16, boxShadow: cardShadow }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10, color }}>
        <Icon size={15} /> <span style={{ fontSize: 13, fontWeight: 700 }}>{title}</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {list.map((s, i) => (
          <div key={s.t} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "7px 2px", borderBottom: i < list.length - 1 ? `1px solid ${C.line}` : "none" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 10.5, color: C.textFaint, width: 14 }}>{i + 1}</span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: 12.5 }}>{s.t}</span>
            </div>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12.5, fontWeight: 700, color }}>{fmtPct(s.dayChange)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* NEW: Sector rollup — week-over-week, weighted by discussion volume   */
/* ------------------------------------------------------------------ */
function SectorPanel({ stocks }) {
  const sectors = useMemo(() => {
    const map = {};
    stocks.forEach((s) => {
      if (!map[s.sector]) map[s.sector] = { sector: s.sector, tickers: [], totalMentions: 0, weighted: 0 };
      map[s.sector].tickers.push(s);
      map[s.sector].totalMentions += s.totalMentions;
      map[s.sector].weighted += s.weekChange * s.totalMentions;
    });
    return Object.values(map)
      .map((g) => ({ ...g, avgWeekChange: g.weighted / g.totalMentions }))
      .sort((a, b) => b.avgWeekChange - a.avgWeekChange);
  }, [stocks]);

  const maxAbs = Math.max(...sectors.map((s) => Math.abs(s.avgWeekChange)), 1);

  return (
    <div style={{ marginBottom: 26 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <Layers size={18} color={C.gold} />
        <h2 style={{ fontSize: 17, fontWeight: 800, margin: 0 }}>סקטורים — עלייה/ירידה משבוע לשבוע</h2>
      </div>
      <p style={{ fontSize: 12.5, color: C.textMuted, margin: "4px 0 18px" }}>
        ממוצע השינוי השבועי של המניות המדוברות בכל סקטור, משוקלל לפי נפח האזכורים שלהן ברדיט.
      </p>

      <div style={{ background: cardBg, border: `1px solid ${C.line}`, borderRadius: 16, boxShadow: cardShadow, padding: 16 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {sectors.map((sec) => {
            const up = sec.avgWeekChange >= 0;
            const barPct = (Math.abs(sec.avgWeekChange) / maxAbs) * 50;
            return (
              <div key={sec.sector} style={{ display: "grid", gridTemplateColumns: "128px 1fr 62px", gap: 12, alignItems: "center" }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 700, color: C.textPrimary }}>{sec.sector}</span>
                  <span style={{ fontSize: 10.5, color: C.textFaint }}>{sec.tickers.length} מניות · {sec.totalMentions} אזכורים</span>
                </div>

                <div dir="ltr" style={{ position: "relative", height: 22 }}>
                  <div style={{ position: "absolute", inset: 0, background: "rgba(255,255,255,0.04)", borderRadius: 6 }} />
                  <div style={{ position: "absolute", top: 0, bottom: 0, left: "50%", width: 1, background: C.lineStrong }} />
                  <div style={{
                    position: "absolute", top: 2, bottom: 2, borderRadius: 4,
                    left: up ? "50%" : `${50 - barPct}%`, width: `${barPct}%`,
                    background: up ? C.gain : C.loss, opacity: 0.85,
                  }} />
                </div>

                <span style={{
                  fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: 12.5, textAlign: "left",
                  color: up ? C.gain : C.loss,
                }}>{fmtPct(sec.avgWeekChange)}</span>

                <div style={{ gridColumn: "2 / 3", display: "flex", gap: 6, flexWrap: "wrap", marginTop: -4 }}>
                  {sec.tickers.sort((a, b) => b.totalMentions - a.totalMentions).map((t) => (
                    <span key={t.t} style={{
                      fontSize: 10, fontFamily: "'JetBrains Mono', monospace", color: t.weekChange >= 0 ? C.gain : C.loss,
                      background: t.weekChange >= 0 ? C.gainDim : C.lossDim, padding: "2px 7px", borderRadius: 999,
                    }}>{t.t}</span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* NEW: Week-over-week comparison feature                               */
/* ------------------------------------------------------------------ */
function WeekComparePanel({ stocks }) {
  const rows = useMemo(() => {
    return [...stocks]
      .sort((a, b) => b.lastWeekMentions - a.lastWeekMentions)
      .slice(0, 10)
      .map((s) => {
        const ratio = s.totalMentions / s.lastWeekMentions;
        const status = ratio >= 0.75 ? "hot" : ratio >= 0.35 ? "cooling" : "faded";
        return { ...s, ratio, status };
      });
  }, [stocks]);

  const statusMeta = {
    hot: { label: "עדיין ברדאר", color: C.gold, bg: C.goldDim },
    cooling: { label: "מתקרר", color: C.subStocks, bg: "rgba(110,155,255,0.12)" },
    faded: { label: "ירד מהרדאר", color: C.textMuted, bg: "rgba(255,255,255,0.05)" },
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <History size={18} color={C.gold} />
        <h2 style={{ fontSize: 17, fontWeight: 800, margin: 0 }}>מה בער לפני שבוע — ואיך זה הגיב מאז</h2>
      </div>
      <p style={{ fontSize: 12.5, color: C.textMuted, margin: "4px 0 18px" }}>
        10 המניות עם הכי הרבה אזכורים לפני 7 ימים, מול הביצועים שלהן מאז ומצב הבאזז הנוכחי סביבן.
      </p>

      <div style={{ background: cardBg, border: `1px solid ${C.line}`, borderRadius: 16, boxShadow: cardShadow, overflow: "hidden" }}>
        {/* header row */}
        <div style={{
          display: "grid", gridTemplateColumns: "28px 1.3fr 1fr 1fr 0.9fr 1fr", gap: 8, padding: "10px 16px",
          borderBottom: `1px solid ${C.lineStrong}`, fontSize: 11, color: C.textFaint,
        }}>
          <span>#</span><span>מניה</span><span>אזכורים אז → היום</span><span>מחיר אז → היום</span><span>שינוי</span><span>סטטוס</span>
        </div>
        {rows.map((s, i) => {
          const meta = statusMeta[s.status];
          const up = s.weekChange >= 0;
          return (
            <div key={s.t} style={{
              display: "grid", gridTemplateColumns: "28px 1.3fr 1fr 1fr 0.9fr 1fr", gap: 8, padding: "12px 16px",
              alignItems: "center", borderBottom: i < rows.length - 1 ? `1px solid ${C.line}` : "none",
            }}>
              <span style={{ fontSize: 11, color: C.textFaint }}>{i + 1}</span>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 800, fontSize: 13.5 }}>{s.t}</span>
                <span style={{ fontSize: 10.5, color: C.textMuted }}>{s.name}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 5, fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}>
                <span style={{ color: C.textMuted }}>{s.lastWeekMentions}</span>
                <Minus size={10} color={C.textFaint} style={{ transform: "rotate(90deg)" }} />
                <span style={{ color: C.textPrimary, fontWeight: 700 }}>{s.totalMentions}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 5, fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}>
                <span style={{ color: C.textMuted }}>{fmt$(s.priceLastWeek)}</span>
                <Minus size={10} color={C.textFaint} style={{ transform: "rotate(90deg)" }} />
                <span style={{ color: C.textPrimary, fontWeight: 700 }}>{fmt$(s.price)}</span>
              </div>
              <span style={{
                fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: 12.5, color: up ? C.gain : C.loss,
              }}>{fmtPct(s.weekChange)}</span>
              <span style={{
                fontSize: 10.5, fontWeight: 700, color: meta.color, background: meta.bg, padding: "3px 9px",
                borderRadius: 999, width: "fit-content",
              }}>{meta.label}</span>
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "flex-start", marginTop: 12, fontSize: 11.5, color: C.textMuted }}>
        <ShieldAlert size={14} style={{ marginTop: 1, flexShrink: 0 }} />
        <span>"עדיין ברדאר" = כמות האזכורים היום נשארה 75%+ מרמת השיא של לפני שבוע. "ירד מהרדאר" = צנחה מתחת ל-35%.</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* App                                                                  */
/* ------------------------------------------------------------------ */
export default function App() {
  const stocks = useMemo(() => BASE.map((b, i) => buildStock(b, i)), []);
  const [expandedTicker, setExpandedTicker] = useState(null);
  const [view, setView] = useState("today");

  const gainers = [...stocks].sort((a, b) => b.dayChange - a.dayChange).slice(0, 10);
  const losers = [...stocks].sort((a, b) => a.dayChange - b.dayChange).slice(0, 10);
  const byMentions = [...stocks].sort((a, b) => b.totalMentions - a.totalMentions);

  const handlePick = (ticker) => {
    setView("today");
    setExpandedTicker((cur) => (cur === ticker ? null : ticker));
    setTimeout(() => {
      const el = document.getElementById(`card-${ticker}`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 60);
  };

  const today = new Date().toLocaleDateString("he-IL", { weekday: "long", day: "numeric", month: "long" });

  return (
    <div dir="rtl" style={{
      background: `radial-gradient(ellipse at 50% -10%, #161B26 0%, ${C.void} 55%)`,
      minHeight: "100vh", color: C.textPrimary, fontFamily: "'Heebo', sans-serif",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700;800&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');
        * { box-sizing: border-box; }
        button:focus-visible { outline: 2px solid ${C.gold}; outline-offset: 2px; }
        ::-webkit-scrollbar { height: 6px; width: 6px; }
        ::-webkit-scrollbar-thumb { background: ${C.lineStrong}; border-radius: 4px; }
      `}</style>

      {/* Header */}
      <div style={{ borderBottom: `1px solid ${C.line}`, padding: "18px 20px", backdropFilter: "blur(6px)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <span style={{ width: 8, height: 8, borderRadius: 99, background: C.gain, display: "inline-block", boxShadow: `0 0 8px ${C.gain}` }} />
              <h1 style={{
                fontSize: 21, fontWeight: 800, margin: 0,
                background: `linear-gradient(90deg, ${C.textPrimary}, ${C.gold})`,
                WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
              }}>Stock Pulse — דופק הרשת</h1>
            </div>
            <p style={{ fontSize: 12, color: C.textMuted, margin: "5px 0 0" }}>{today} · המניות שהכי הדהדו היום ב-Reddit</p>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {Object.entries(SUB_META).map(([k, v]) => (
              <span key={k} style={{ display: "flex", alignItems: "center", gap: 5, padding: "5px 11px", borderRadius: 999, border: `1px solid ${C.line}`, fontSize: 11, background: "rgba(255,255,255,0.02)" }}>
                <span style={{ width: 6, height: 6, borderRadius: 99, background: v.color }} /> {v.label}
              </span>
            ))}
          </div>
        </div>

        {/* view tabs */}
        <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
          {[{ id: "today", label: "היום", icon: Flame }, { id: "week", label: "שבוע שעבר ← היום", icon: History }].map((v) => (
            <button key={v.id} onClick={() => setView(v.id)}
              style={{
                display: "flex", alignItems: "center", gap: 7, padding: "8px 16px", borderRadius: 10, cursor: "pointer",
                border: `1px solid ${view === v.id ? C.gold : C.line}`,
                background: view === v.id ? C.goldDim : "transparent",
                color: view === v.id ? C.gold : C.textMuted, fontSize: 13, fontWeight: 700,
                transition: "all .15s",
              }}>
              <v.icon size={14} /> {v.label}
            </button>
          ))}
        </div>
      </div>

      {view === "today" ? (
        <>
          {/* Pulse rail */}
          <div style={{ padding: "0 20px" }}>
            <div style={{ marginTop: 14 }}><SectionEyebrow>🔥 הכי חמות עכשיו</SectionEyebrow></div>
            <PulseRail stocks={stocks} onPick={handlePick} />
          </div>

          {/* Body */}
          <div style={{ padding: 20, display: "grid", gridTemplateColumns: "300px 1fr", gap: 18, alignItems: "start" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 14, position: "sticky", top: 20 }}>
              <MoversColumn title="10 העולות ביותר היום" list={gainers} color={C.gain} icon={TrendingUp} />
              <MoversColumn title="10 היורדות ביותר היום" list={losers} color={C.loss} icon={TrendingDown} />
            </div>

            <div>
              <SectionEyebrow>כל המניות המדוברות, ממוינות לפי מספר אזכורים</SectionEyebrow>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {byMentions.map((s) => (
                  <div id={`card-${s.t}`} key={s.t}>
                    <StockCard s={s} expanded={expandedTicker === s.t} onToggle={() => setExpandedTicker((c) => (c === s.t ? null : s.t))} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      ) : (
        <div style={{ padding: 20, maxWidth: 900 }}>
          <SectorPanel stocks={stocks} />
          <WeekComparePanel stocks={stocks} />
        </div>
      )}

      <div style={{ padding: "10px 20px 26px", fontSize: 11, color: C.textFaint, lineHeight: 1.7, borderTop: `1px solid ${C.line}`, marginTop: 10 }}>
        פרוטוטייפ להמחשה בלבד — כל הנתונים (אזכורים, מחירים, נתונים פיננסיים ורמות טכניות) הם נתוני דוגמה שנוצרו אקראית ואינם משקפים מציאות. אין לראות בתוכן ייעוץ השקעות מכל סוג.
      </div>
    </div>
  );
}
