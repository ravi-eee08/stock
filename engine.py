# engine.py - shared logic for the app (swing_desk.py) and the alert worker (alerts.py)
import os, json, time
import pandas as pd, numpy as np, yfinance as yf
from datetime import date

WL, LEDGER, COST = "watchlist.json", "paper_ledger.csv", 0.0015
COLS = ["date", "symbol", "side", "qty", "price", "stop", "target"]
_C = {}

def load(sym):
    t, d = _C.get(sym, (0, None))
    if d is not None and time.time() - t < 600: return d
    df = yf.download(sym, period="2y", auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = df.dropna(); _C[sym] = (time.time(), df); return df

def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def indicators(df):
    d, c = df.copy(), df.Close
    for n in (20, 50, 200): d[f"EMA{n}"] = ema(c, n)
    dl = c.diff()
    up = dl.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    dn = (-dl.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    d["RSI"] = 100 - 100 / (1 + up / dn)
    m = ema(c, 12) - ema(c, 26)
    d["MACDh"] = m - ema(m, 9)
    tr = pd.concat([d.High - d.Low, (d.High - c.shift()).abs(), (d.Low - c.shift()).abs()], axis=1).max(axis=1)
    d["ATR"] = tr.ewm(alpha=1/14, adjust=False).mean()
    return d

def score(d, bench_ret):
    r = d.iloc[-1]
    checks = [
        (r.Close > r.EMA50, 20, "Above 50 EMA"),
        (r.Close > r.EMA200, 20, "Above 200 EMA"),
        (r.EMA20 > r.EMA50, 15, "20 EMA > 50 EMA"),
        (50 <= r.RSI <= 70, 15, "RSI 50-70"),
        (r.MACDh > 0, 15, "MACD histogram positive"),
        (r.Close / d.Close.iloc[-64] - 1 > bench_ret, 15, "Beating Nifty (3m)"),
    ]
    return sum(p for ok, p, _ in checks if ok), [w for ok, _, w in checks if ok]

def xirr(cfs):
    t0 = cfs[0][0]
    f = lambda r: sum(a / (1 + r) ** ((d - t0).days / 365) for d, a in cfs)
    lo, hi = -0.99, 10.0
    if f(lo) * f(hi) > 0: return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0: hi = mid
        else: lo = mid
    return mid


# ---------- watchlist ----------
def get_watchlist(default=""):
    if os.path.exists(WL): return json.load(open(WL))
    l = [x.strip().upper() for x in default.split(",") if x.strip()]
    if l: save_watchlist(l)
    return l

def save_watchlist(l): json.dump(sorted(set(l)), open(WL, "w"))

def search_symbols(q):
    out = []
    try:
        for r in yf.Search(q, max_results=15).quotes:
            sy = r.get("symbol", "")
            if sy.endswith(".NS"): out.append((sy[:-3], r.get("shortname") or r.get("longname") or ""))
    except Exception: pass
    return out

# ---------- virtual ledger ----------
def read_ledger():
    return pd.read_csv(LEDGER) if os.path.exists(LEDGER) else pd.DataFrame(columns=COLS)

def write_ledger(df): df.to_csv(LEDGER, index=False)

def book(led):
    """Returns (cash, open positions, fund flows for XIRR). Rows: BUY, SELL, DEPOSIT, WITHDRAW."""
    cash, pos, flows = 0.0, {}, []
    for r in led.itertuples():
        d = pd.to_datetime(r.date).date()
        if r.side == "DEPOSIT": cash += r.price; flows.append((d, -float(r.price)))
        elif r.side == "WITHDRAW": cash -= r.price; flows.append((d, float(r.price)))
        else:
            p = pos.setdefault(r.symbol, dict(q=0, c=0.0, stop=r.stop, tgt=r.target))
            if r.side == "BUY":
                cash -= r.qty * r.price * (1 + COST)
                p["c"] = (p["c"] * p["q"] + r.price * r.qty) / (p["q"] + r.qty)
                p["q"] += r.qty; p["stop"], p["tgt"] = r.stop, r.target
            else:
                cash += r.qty * r.price * (1 - COST); p["q"] -= r.qty
    return cash, {k: v for k, v in pos.items() if v["q"] > 0}, sorted(flows)

# ---------- alert rules (shared by app and alerts.py) ----------
def live(syms):
    out = {}
    if not syms: return out
    df = yf.download([s + ".NS" for s in syms], period="1d", interval="1m", progress=False, group_by="ticker")
    for s in syms:
        try: out[s] = float(df[s + ".NS"].Close.dropna().iloc[-1])
        except Exception: pass
    return out

def signals(wl, pos, sc, px, min_score=65):
    """sc = {symbol: (score, atr)}, px = live prices. Returns [(key, kind, symbol, message)]."""
    out = []
    for s, v in pos.items():
        p = px.get(s)
        if p is None: continue
        if p <= v["stop"]: out.append((f"{s}-stop", "SELL", s, f"SELL {s}: stop hit. Price {p:.2f} <= stop {v['stop']:.2f}"))
        elif p >= v["tgt"]: out.append((f"{s}-tgt", "BOOK", s, f"BOOK PROFIT {s}: target reached. Price {p:.2f} >= {v['tgt']:.2f}"))
        elif s in sc and sc[s][0] < 45: out.append((f"{s}-weak", "SELL", s, f"SELL {s}: trend score fell to {sc[s][0]}"))
    for s in wl:
        if s not in pos and s in sc and sc[s][0] >= min_score and s in px:
            p, a = px[s], sc[s][1]
            out.append((f"{s}-buy", "BUY", s, f"BUY signal {s}: score {sc[s][0]}. Price {p:.2f}, stop {p - 2 * a:.2f}, target {p + 4 * a:.2f}"))
    return out

# ---------- market-wide scan + news ----------
FALLBACK = ("RELIANCE TCS HDFCBANK ICICIBANK INFY SBIN BHARTIARTL ITC LT AXISBANK KOTAKBANK HCLTECH SUNPHARMA MARUTI NTPC POWERGRID "
 "ONGC COALINDIA TATASTEEL JSWSTEEL HINDALCO ADANIENT ADANIPORTS ADANIPOWER ADANIGREEN BAJFINANCE BAJAJFINSV TITAN ASIANPAINT "
 "ULTRACEMCO NESTLEIND HINDUNILVR WIPRO TECHM TATAELXSI PERSISTENT COFORGE MPHASIS DIXON POLYCAB HAL BEL MAZDOCK BHEL BDL COCHINSHIP "
 "GRSE DATAPATTNS SUZLON WAAREEENER INOXWIND TRENT DLF LODHA GODREJPROP IRFC RVNL IRCON PFC RECLTD HUDCO CANBK PNB BANKBARODA "
 "UNIONBANK FEDERALBNK IDFCFIRSTB BSE CDSL ANGELONE MCX KALYANKJIL NATIONALUM VEDL SAIL NMDC JIOFIN POONAWALLA CHOLAFIN MUTHOOTFIN "
 "DRREDDY CIPLA LUPIN DIVISLAB APOLLOHOSP MAXHEALTH").split()

def universe():
    try:
        df = pd.read_csv("https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
                         storage_options={"User-Agent": "Mozilla/5.0"})
        return sorted(df["Symbol"].dropna().astype(str).tolist())
    except Exception: return FALLBACK

def scan(symbols):
    n = indicators(load("^NSEI")); bench = n.Close.iloc[-1] / n.Close.iloc[-64] - 1
    data = yf.download([s + ".NS" for s in symbols], period="1y", auto_adjust=True, group_by="ticker", threads=True, progress=False)
    rows = []
    for s in symbols:
        try:
            d = data[s + ".NS"].dropna()
            if len(d) < 120: continue
            d = indicators(d); sc, why = score(d, bench); r = d.iloc[-1]
            rows.append({"Symbol": s, "Price": round(float(r.Close), 2), "Score": sc,
                         "1M %": round((r.Close / d.Close.iloc[-22] - 1) * 100, 1),
                         "3M %": round((r.Close / d.Close.iloc[-64] - 1) * 100, 1), "Why": ", ".join(why)})
        except Exception: pass
    return pd.DataFrame(rows).sort_values(["Score", "3M %"], ascending=False)

POS_W, NEG_W = "surge jump gain rise beat record profit growth order win upgrade buy".split(), "fall drop loss cut miss probe fraud downgrade sell decline".split()
def news(sym, n=3):
    out = []
    try:
        for it in yf.Ticker(sym + ".NS").news[:n]:
            t = (it.get("content") or {}).get("title") or it.get("title") or ""
            w = t.lower(); k = sum(x in w for x in POS_W) - sum(x in w for x in NEG_W)
            out.append(("[+] " if k > 0 else "[-] " if k < 0 else "[ ] ") + t)
    except Exception: pass
    return out

def recommend(d, sc, risk_on, heads):
    """Overall view from chart score + market regime + news tone. Returns (verdict, rating, reasons, levels)."""
    r = d.iloc[-1]; c = float(r.Close)
    tilt = sum(h.startswith("[+]") for h in heads) - sum(h.startswith("[-]") for h in heads)
    comp = sc + (0 if risk_on else -15) + max(-10, min(10, 5 * tilt))
    hi52 = float(d.High.tail(250).max())
    why = []
    if r.RSI > 75: comp -= 10; why.append(f"RSI {r.RSI:.0f} is overheated, a pullback is likely, so wait for a dip")
    why.append("Price is above the 200-day average (long-term uptrend)" if c > r.EMA200 else "Price is below the 200-day average (long-term downtrend)")
    why.append("Short-term trend is positive (20 EMA above 50 EMA)" if r.EMA20 > r.EMA50 else "Short-term trend is weak (20 EMA below 50 EMA)")
    why.append(f"RSI {r.RSI:.0f}, MACD momentum {'rising' if r.MACDh > 0 else 'falling'}")
    why.append(f"Trading {(c / hi52 - 1) * 100:.0f}% from its 1-year high")
    why.append("Market is risk-on (Nifty above its 200-day average)" if risk_on else "Market is risk-off (Nifty below its 200-day average), so be cautious with new buys")
    why.append("News tone: " + ("mostly positive" if tilt > 0 else "mostly negative" if tilt < 0 else "neutral or unclear") + " (keyword based)")
    comp = max(0, min(100, comp))
    verdict = ("BUY ON DIP (strong but overheated)" if r.RSI > 75 and comp >= 60 else "BUY" if comp >= 70 else
               "WATCH, accumulate on dips" if comp >= 55 else "HOLD, avoid new buys" if comp >= 40 else "SELL / AVOID")
    a = float(r.ATR)
    return verdict, comp, why, dict(price=c, support=float(d.Low.tail(20).min()), resistance=float(d.High.tail(20).max()), stop=c - 2 * a, target=c + 4 * a)
