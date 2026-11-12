# alerts.py - background watcher. Run in a second terminal:  python alerts.py
# Needs (set as environment variables): TELEGRAM_TOKEN, TELEGRAM_CHAT_ID  (free, instant)
# Optional SMS via Fast2SMS: FAST2SMS_KEY, SMS_NUMBER.  Optional: MIN_SCORE (65), CHECK_SECONDS (60), ALWAYS=1 (test outside market hours)
import os, time, json, requests, datetime as dt
import yfinance as yf
from engine import *

clean = lambda v: (v or "").strip().strip("\"\'<> ")
TOKEN, CHAT = clean(os.getenv("TELEGRAM_TOKEN")), clean(os.getenv("TELEGRAM_CHAT_ID"))
SMS_KEY, SMS_NUM = os.getenv("FAST2SMS_KEY"), os.getenv("SMS_NUMBER")
MIN_SCORE, EVERY, STATE = int(os.getenv("MIN_SCORE", 65)), int(os.getenv("CHECK_SECONDS", 60)), "alert_state.json"
sent = json.load(open(STATE)) if os.path.exists(STATE) else {}

def notify(key, msg):
    k = f"{dt.date.today()}|{key}"
    if k in sent: return
    print(msg); ok = not (TOKEN or SMS_KEY)
    try:
        if TOKEN:
            r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT, "text": msg}, timeout=10)
            print("  Telegram:", r.status_code, r.text[:150]); ok = ok or r.ok
        if SMS_KEY:
            r = requests.get("https://www.fast2sms.com/dev/bulkV2", headers={"authorization": SMS_KEY}, timeout=10,
                             params={"route": "q", "message": msg[:150], "language": "english", "flash": 0, "numbers": SMS_NUM})
            print("  SMS:", r.status_code, r.text[:150]); ok = ok or r.ok
    except Exception as e: print("  notify failed:", e)
    if ok: sent[k] = 1; json.dump(sent, open(STATE, "w"))

def market_open():
    n = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    return os.getenv("ALWAYS") or (n.weekday() < 5 and dt.time(9, 15) <= n.time() <= dt.time(15, 30))

def live(syms):
    out = {}
    df = yf.download([s + ".NS" for s in syms], period="1d", interval="1m", progress=False, group_by="ticker")
    for s in syms:
        try: out[s] = float(df[s + ".NS"].Close.dropna().iloc[-1])
        except Exception: pass
    return out

def daily(syms):
    n = indicators(load("^NSEI")); bench = n.Close.iloc[-1] / n.Close.iloc[-64] - 1; out = {}
    for s in syms:
        try:
            d = indicators(load(s + ".NS")); out[s] = (score(d, bench)[0], float(d.iloc[-1].ATR))
        except Exception: pass
    return out

last, sc = 0, {}
print("Alert worker started. Token length:", len(TOKEN), "(should be about 46) | Telegram token set:", bool(TOKEN), "| chat id set:", bool(CHAT), "| Ctrl+C to stop.")
while True:
    try:
        if market_open():
            wl = get_watchlist(); cash, pos, _ = book(read_ledger()); watch = sorted(set(wl) | set(pos))
            if time.time() - last > 1800: sc, last = daily(watch), time.time()
            px = live(watch)
            for s, v in pos.items():
                p = px.get(s)
                if p is None: continue
                if p <= v["stop"]: notify(f"{s}-stop", f"SELL {s}: stop hit. Price {p:.2f} <= stop {v['stop']:.2f}")
                elif p >= v["tgt"]: notify(f"{s}-tgt", f"BOOK PROFIT {s}: target reached. Price {p:.2f} >= {v['tgt']:.2f}")
                elif s in sc and sc[s][0] < 45: notify(f"{s}-weak", f"SELL {s}: trend score fell to {sc[s][0]}")
            for s in wl:
                if s not in pos and s in sc and sc[s][0] >= MIN_SCORE and s in px:
                    p = px[s]; notify(f"{s}-buy", f"BUY signal {s}: score {sc[s][0]}. Price {p:.2f}, stop {p - 2 * sc[s][1]:.2f}, target {p + 4 * sc[s][1]:.2f}")
    except Exception as e: print("loop error", e)
    time.sleep(EVERY)
