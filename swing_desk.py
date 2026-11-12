# Swing Desk - tabs: Watchlist | Chart | Suggestions | My portfolio | Top performers
import streamlit as st
st.set_page_config(page_title="Swing Desk", layout="wide")
from engine import *
import plotly.graph_objects as go
from plotly.subplots import make_subplots

load = st.cache_data(ttl=900)(load); live_px = st.cache_data(ttl=60)(live)
scan_c = st.cache_data(ttl=1800)(scan); news_c = st.cache_data(ttl=1800)(news); uni_c = st.cache_data(ttl=86400)(universe)
DEFAULTS = ("BSE, JIOFIN, KALYANKJIL, AXISCADES, DELTACORP, IMAGICAA, DATAPATTNS, BHEL, SUZLON, MAZDOCK, POONAWALLA, HDBFS, "
            "TECHM, INFY, HCLTECH, ADANIENT, ADANIPORTS, ADANIPOWER, ADANIGREEN, LT, SBIN, BEL, HAL, WAAREEENER, "
            "TATAELXSI, SUNPHARMA, TMPV, TMCV, NATIONALUM")
SECTOR = {**{k: "Defence/Capex" for k in "HAL BEL MAZDOCK DATAPATTNS BHEL AXISCADES LT".split()},
          **{k: "IT" for k in "TECHM INFY HCLTECH TATAELXSI".split()},
          **{k: "Adani" for k in "ADANIENT ADANIPORTS ADANIPOWER ADANIGREEN".split()},
          **{k: "Renewables" for k in "SUZLON WAAREEENER".split()},
          **{k: "Financials" for k in "BSE JIOFIN POONAWALLA HDBFS SBIN".split()},
          **{k: "Auto" for k in ["TMPV", "TMCV"]}, **{k: "Leisure" for k in "KALYANKJIL DELTACORP IMAGICAA".split()}}
colour = lambda v: "color:#16a34a" if v > 0 else ("color:#dc2626" if v < 0 else "")

with st.sidebar:
    st.header("Settings")
    syms = get_watchlist(DEFAULTS)
    capital = st.number_input("Capital for sizing (Rs)", 50000, 100000000, 300000, 25000)
    risk_pct = st.slider("Risk per trade (% of capital)", 0.5, 2.5, 1.0, 0.25)
    max_pos = st.slider("Max positions", 3, 15, 7)
    max_pct = st.slider("Max % in one stock", 5, 25, 20)
    cash_pct = st.slider("Cash buffer %", 0, 40, 15)
    sector_cap = st.slider("Max stocks per theme", 1, 4, 2)
    min_score = st.slider("Min score to buy", 40, 90, 65)
    atr_mult = st.slider("Stop distance (x ATR)", 1.0, 3.5, 2.0, 0.5)

nifty = indicators(load("^NSEI")); nr = nifty.iloc[-1]
bench_ret = nifty.Close.iloc[-1] / nifty.Close.iloc[-64] - 1
risk_on = nr.Close > nr.EMA200
factor = 1.0 if (risk_on and nr.EMA50 > nr.EMA200) else (0.7 if risk_on else 0.4)
st.title("Swing Desk")
c1, c2, c3 = st.columns(3)
c1.metric("Nifty 50", f"{nr.Close:,.0f}", f"{(nr.Close / nifty.Close.iloc[-2] - 1) * 100:.2f}% today")
c2.metric("Regime", "Risk-on" if risk_on else "Risk-off", "Above 200 EMA" if risk_on else "Below 200 EMA")
c3.metric("Deployable", f"{factor * 100:.0f}%", "of non-cash capital")

res = {}
with st.spinner("Analysing watchlist..."):
    for s in syms:
        try:
            d = indicators(load(s + ".NS")); sc, why = score(d, bench_ret); r = d.iloc[-1]
            res[s] = dict(sym=s, d=d, score=sc, why=why, close=float(r.Close), prev=float(d.Close.iloc[-2]), atr=float(r.ATR))
        except Exception: st.warning(f"No data for {s}")
cash, hpos, flows = book(read_ledger())
px = live_px(tuple(sorted(set(res) | set(hpos))))
t1, t2, t3, t4, t5 = st.tabs(["Watchlist", "Chart", "Suggestions", "My portfolio", "Top performers"])

# ---------------- Watchlist ----------------
with t1:
    rows = []
    for s, x in res.items():
        ltp = px.get(s, x["close"]); ch = ltp - x["prev"]
        rows.append({"Symbol": s, "LTP": ltp, "Change": ch, "Change %": ch / x["prev"] * 100, "Score": x["score"],
                     "Signal": "Buy zone" if x["score"] >= min_score else ("Watch" if x["score"] >= 45 else "Avoid")})
    if rows:
        sty = pd.DataFrame(rows).style
        sty = (sty.map if hasattr(sty, "map") else sty.applymap)(colour, subset=["Change", "Change %"])
        st.dataframe(sty.format({"LTP": "{:,.2f}", "Change": "{:+.2f}", "Change %": "{:+.2f}%"}), use_container_width=True, hide_index=True, height=560)
    st.caption(f"{len(res)} stocks. Prices refresh about every minute (Yahoo data can lag a little).")
    with st.expander("Add / delete stocks"):
        q = st.text_input("Search by name or symbol")
        if q:
            for sy, nm in (search_symbols(q) or [(q.strip().upper(), "add by exact NSE symbol")]):
                a, b = st.columns([4, 1]); a.write(f"**{sy}**  {nm}")
                if b.button("Add", key=f"add{sy}") and sy not in syms: save_watchlist(syms + [sy]); st.rerun()
        rm = st.multiselect("Remove stocks", syms)
        if st.button("Delete selected") and rm: save_watchlist([z for z in syms if z not in rm]); st.rerun()

# ---------------- Chart ----------------
with t2:
    q = st.text_input("Search any NSE stock by name or symbol (for example: waaree, tata power, irfc)")
    if q:
        hits = search_symbols(q) or [(q.strip().upper(), "exact symbol")]
        names = dict(hits)
        pick = st.selectbox("Search results", list(names), format_func=lambda s: f"{s}  {names[s]}")
    else:
        opts = sorted(set(syms) | set(uni_c()))
        pick = st.selectbox("Or choose from your list and the Nifty 500 (type to filter)", opts,
                            index=opts.index(syms[0]) if syms and syms[0] in opts else 0)
    d = None
    try:
        if pick in res: d, sc = res[pick]["d"], res[pick]["score"]
        else:
            d = indicators(load(pick + ".NS")); sc, _ = score(d, bench_ret)
    except Exception: st.error(f"No data found for {pick}")
    if d is not None:
        heads = news_c(pick, 5)
        verdict, rating, why, lv = recommend(d, sc, risk_on, heads)
        (st.success if verdict.startswith("BUY") else st.error if verdict.startswith("SELL") else st.warning)(
            f"**{pick}: {verdict}**   |   Trend score {sc}/100   |   Overall rating {rating}/100 (chart + market + news)")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Price", f"{lv['price']:,.2f}"); m2.metric("Support (20d low)", f"{lv['support']:,.2f}")
        m3.metric("Resistance (20d high)", f"{lv['resistance']:,.2f}"); m4.metric("Suggested stop", f"{lv['stop']:,.2f}")
        m5.metric("Suggested target", f"{lv['target']:,.2f}")
        t = d.tail(180)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=t.index, open=t.Open, high=t.High, low=t.Low, close=t.Close, name="Price"), 1, 1)
        for n in (20, 50, 200): fig.add_trace(go.Scatter(x=t.index, y=t[f"EMA{n}"], name=f"EMA{n}", line=dict(width=1)), 1, 1)
        fig.add_trace(go.Scatter(x=t.index, y=t.RSI, name="RSI"), 2, 1)
        fig.add_hline(y=70, row=2, col=1, line_dash="dot"); fig.add_hline(y=30, row=2, col=1, line_dash="dot")
        fig.update_layout(height=560, xaxis_rangeslider_visible=False, margin=dict(t=20))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("**Why this view**")
        for w in why: st.write("- " + w)
        with st.expander("Latest headlines"):
            for h in heads or ["No headlines found"]: st.write(h)
        st.caption("A rule-based view from charts, the market trend and headline keywords. It is not investment advice, and it ignores earnings and valuation.")

# ---------------- Suggestions ----------------
with t3:
    for m in st.session_state.pop("msgs", []): st.info(m)
    deploy = capital * (1 - cash_pct / 100) * factor
    rows, cnt = [], {}
    for x in sorted(res.values(), key=lambda x: -x["score"]):
        s = x["sym"]; sec = SECTOR.get(s, s)
        if s in hpos or x["score"] < min_score or sum(r["Action"] == "BUY" for r in rows) >= max_pos or cnt.get(sec, 0) >= sector_cap: continue
        cnt[sec] = cnt.get(sec, 0) + 1
        p = px.get(s, x["close"]); stop = p - atr_mult * x["atr"]; rk = p - stop
        q = min(int(capital * risk_pct / 100 / rk), int(capital * max_pct / 100 / p))
        rows.append(dict(Execute=False, Symbol=s, Action="BUY", Qty=q, Price=round(p, 2), CMP=round(p, 2), Stop=round(stop, 2),
                         Target=round(p + 2 * rk, 2), Score=x["score"], Note="Trend buy zone"))
    tot = sum(r["Qty"] * r["Price"] for r in rows)
    if tot > deploy > 0:
        for r in rows: r["Qty"] = int(r["Qty"] * deploy / tot)
    for s, v in hpos.items():
        p = px.get(s, v["c"]); sc = res.get(s, {}).get("score", 100)
        why = "Stop hit" if p <= v["stop"] else "Target reached" if p >= v["tgt"] else "Trend weak" if sc < 45 else None
        if why: rows.append(dict(Execute=False, Symbol=s, Action="SELL", Qty=int(v["q"]), Price=round(p, 2), CMP=round(p, 2),
                                 Stop=v["stop"], Target=v["tgt"], Score=sc, Note=why))
    st.write(f"Free virtual cash: **Rs {cash:,.0f}**. Edit Action, Qty, Price, Stop or Target, tick Execute, then press the button.")
    if rows:
        ed = st.data_editor(pd.DataFrame(rows), hide_index=True, use_container_width=True, key="sug",
                            disabled=["Symbol", "CMP", "Score", "Note"],
                            column_config={"Execute": st.column_config.CheckboxColumn(), "Action": st.column_config.SelectboxColumn(options=["BUY", "SELL"])})
        if st.button("Execute selected in my portfolio"):
            L = read_ledger(); c0, p0, _ = book(L); msgs = []
            for r in ed[ed.Execute].itertuples():
                cost = r.Qty * r.Price
                if r.Action == "BUY" and cost * (1 + COST) > c0: msgs.append(f"{r.Symbol}: not enough cash"); continue
                if r.Action == "SELL" and r.Qty > p0.get(r.Symbol, {}).get("q", 0): msgs.append(f"{r.Symbol}: not enough shares to sell"); continue
                L.loc[len(L)] = [date.today().isoformat(), r.Symbol, r.Action, int(r.Qty), float(r.Price), float(r.Stop), float(r.Target)]
                c0 += cost * (1 - COST) if r.Action == "SELL" else -cost * (1 + COST)
                if r.Action == "SELL": p0[r.Symbol]["q"] -= r.Qty
                msgs.append(f"{r.Symbol}: {r.Action} {int(r.Qty)} at {r.Price:.2f} added to portfolio")
            write_ledger(L); st.session_state["msgs"] = msgs or ["Nothing selected"]; st.rerun()
    else: st.info("No suggestions now. Staying in cash is a valid position.")

# ---------------- My portfolio ----------------
with t4:
    f1, f2, f3 = st.columns([2, 1, 1])
    amt = f1.number_input("Fund amount (Rs)", 1000, 100000000, 100000, 5000)
    led = read_ledger()
    if f2.button("Add funds"):
        led.loc[len(led)] = [date.today().isoformat(), "CASH", "DEPOSIT", 1, float(amt), None, None]; write_ledger(led); st.rerun()
    if f3.button("Withdraw"):
        if amt > cash: st.error("Not enough free cash")
        else: led.loc[len(led)] = [date.today().isoformat(), "CASH", "WITHDRAW", 1, float(amt), None, None]; write_ledger(led); st.rerun()
    rows = []
    for s, v in hpos.items():
        ltp = px.get(s, v["c"])
        rows.append({"Symbol": s, "Qty": v["q"], "Avg cost": v["c"], "LTP": ltp, "Value": ltp * v["q"], "P&L": (ltp - v["c"]) * v["q"],
                     "P&L %": (ltp / v["c"] - 1) * 100, "Stop": v["stop"], "Target": v["tgt"]})
    equity = cash + sum(r["Value"] for r in rows); net = -sum(a for _, a in flows)
    a, b, c, d_ = st.columns(4)
    a.metric("Free cash", f"Rs {cash:,.0f}"); b.metric("Total equity", f"Rs {equity:,.0f}")
    c.metric("Profit / loss", f"Rs {equity - net:,.0f}", f"{(equity / net - 1) * 100 if net > 0 else 0:.1f}%")
    xv = xirr(flows + [(date.today(), equity)]) if flows else None
    d_.metric("XIRR", f"{xv * 100:.1f}%" if xv is not None else "n/a", "Target 20-25%", delta_color="off")
    if rows:
        sty = pd.DataFrame(rows).style
        sty = (sty.map if hasattr(sty, "map") else sty.applymap)(colour, subset=["P&L", "P&L %"])
        st.dataframe(sty.format({"Avg cost": "{:,.2f}", "LTP": "{:,.2f}", "Value": "{:,.0f}", "P&L": "{:+,.0f}", "P&L %": "{:+.1f}%"}), use_container_width=True, hide_index=True)
    with st.expander("Trade history and backup"):
        st.dataframe(led.iloc[::-1], use_container_width=True, hide_index=True)
        st.download_button("Download ledger backup", led.to_csv(index=False), "paper_ledger.csv")
        up = st.file_uploader("Restore ledger CSV", type="csv")
        if up is not None and st.button("Restore from this file"): write_ledger(pd.read_csv(up)); st.rerun()

with t4:
    st.divider()
    if st.checkbox("I understand this deletes all my virtual trades and funds") and st.button("Fresh start: clear everything, set funds to Rs 3,00,000"):
        write_ledger(pd.DataFrame([[date.today().isoformat(), "CASH", "DEPOSIT", 1, 300000.0, None, None]], columns=COLS)); st.rerun()

# ---------------- Top performers ----------------
with t5:
    uni = uni_c()
    st.write(f"Scans {len(uni)} NSE stocks (Nifty 500 list when reachable) on trend, momentum and strength vs Nifty, then shows recent headlines.")
    if st.button("Scan market now"):
        with st.spinner("Scanning, this can take a minute or two..."): st.session_state["scan"] = scan_c(tuple(uni))
    if "scan" in st.session_state:
        top = st.session_state["scan"].head(30).copy(); top.insert(0, "Add", False); top["In list"] = top.Symbol.isin(syms)
        ed2 = st.data_editor(top, hide_index=True, use_container_width=True, key="top", disabled=[c for c in top.columns if c != "Add"],
                             column_config={"Add": st.column_config.CheckboxColumn()})
        if st.button("Add selected to my stock list"):
            save_watchlist(syms + ed2[ed2.Add].Symbol.tolist()); st.rerun()
        with st.expander("Latest headlines for the top 8  ([+] positive, [-] negative by keywords)"):
            for s in top.Symbol.head(8):
                st.markdown(f"**{s}**")
                for h in news_c(s) or ["No headlines found"]: st.write(h)
