# What this project is for

This project is a personal **stock research and practice tool** for people following shares listed on India's NSE exchange. It is meant to help a user keep an eye on selected stocks, review simple price trends, and practice managing a portfolio before making any real-world decisions.

## What a user can do

- Keep a list of stocks they want to follow.
- See recent prices, charts, and a score based on a few common trend indicators.
- Review a simple suggestion about whether a stock looks worth watching, buying, or avoiding under the project's rules.
- Practice buying and selling in a virtual portfolio, including tracking cash, shares, estimated gains or losses, and suggested stop and target prices.
- Scan a wider set of NSE stocks for shares that currently match those same trend rules.
- Optionally receive messages when tracked prices or scores meet alert conditions.

The dashboard is the main screen. A separate background program can watch prices and send alerts. Both use the same watchlist and virtual trade history, so the portfolio shown in the dashboard can also guide alerts about holdings.

## How it makes suggestions

The program looks at past prices and calculates moving averages, RSI, MACD momentum, and average price movement. It awards points when selected conditions are met, including whether a stock is performing better than the Nifty over roughly three months. It also considers whether the Nifty is above its long-term average. For chart recommendations, it adds a basic headline tone based on words in recent news headlines.

These are simple, fixed rules. They are intended to organize research and practice, not to predict what a stock will do. The headline check only counts keywords; it does not understand the full meaning of an article.

## What it does not do

- It does not connect to a brokerage account or place real orders.
- Trades entered in the dashboard are practice trades stored on this computer.
- It does not guarantee that a suggested trade will make money or that a stop price will prevent a loss.
- It is not a complete investment service: it does not deeply assess company finances, valuation, taxes, or every market risk.

Market prices and headlines are fetched from Yahoo Finance and may be delayed, incomplete, or unavailable. The project should be treated as a research aid, and users should independently check information before acting on it elsewhere.

## Where its information is kept

The stock list is saved in `watchlist.json`. Practice deposits, withdrawals, buys, and sells are saved in `paper_ledger.csv`. The alert program keeps a small record in `alert_state.json` so it can avoid repeating the same alert on the same day. Optional notification credentials are read from a local `.env` file, which should stay private and is excluded from Git. These are ordinary local files, so users should keep backups if the practice history matters to them.

## In one sentence

Swing Desk helps a user monitor NSE stocks, explore simple trend-based ideas, and practice tracking trades in a virtual portfolio, with optional price alerts.
