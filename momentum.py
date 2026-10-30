"""
Sector Momentum Rotation Strategy - monthly signal + live tracking.

Each month-end:
  1. Measure each of the 9 Select Sector SPDR ETFs' total return over the past 12 months.
  2. Rank them, strongest first.
  3. Hold the top 3 at one-third each for the next month.

Run this script once a month (GitHub Actions does it automatically). It:
  - writes the new picks to latest_signal.md
  - appends them to live_log.csv
  - fills in last month's realized return vs. SPY for the previous picks
"""

import os
import sys
from datetime import date

import pandas as pd

SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
NAMES = {
    "XLB": "Materials", "XLE": "Energy", "XLF": "Financials", "XLI": "Industrials",
    "XLK": "Technology", "XLP": "Consumer Staples", "XLU": "Utilities",
    "XLV": "Health Care", "XLY": "Consumer Discretionary", "SPY": "S&P 500",
}
BENCHMARK = "SPY"
LOOKBACK = 12   # months
TOP_N = 3
LOG_FILE = "live_log.csv"
SIGNAL_FILE = "latest_signal.md"


def load_monthly_prices(start="1998-12-01"):
    """Month-end total-return (dividend-adjusted) prices from Yahoo Finance.
    Drops the current month if it isn't finished yet."""
    local = os.environ.get("PRICES_CSV")  # optional: test with a local file
    if local:
        px = pd.read_csv(local, index_col=0, parse_dates=True)
    else:
        import yfinance as yf
        daily = yf.download(SECTORS + [BENCHMARK], start=start,
                            auto_adjust=True, progress=False)["Close"]
        px = daily.resample("ME").last()
        last_day = daily.index[-1]
        today = pd.Timestamp(date.today())
        if last_day.month == today.month and last_day.year == today.year:
            px = px.iloc[:-1]  # current month still in progress
    px.index = px.index.to_period("M")
    return px[SECTORS + [BENCHMARK]].dropna(how="all")


def rank_sectors(px):
    """Trailing LOOKBACK-month return for each sector at the latest month-end."""
    mom = px[SECTORS].iloc[-1] / px[SECTORS].iloc[-1 - LOOKBACK] - 1
    return mom.sort_values(ascending=False)


def update_log(px, picks):
    month = str(px.index[-1])
    cols = ["signal_month", "holdings", "next_month", "strategy_return", "spy_return", "excess_return"]
    log = pd.read_csv(LOG_FILE, dtype=str) if os.path.exists(LOG_FILE) else pd.DataFrame(columns=cols)

    if month in set(log["signal_month"]):
        print(f"Signal for {month} already logged - nothing to do.")
        return log

    # Fill in the realized return for last month's picks.
    rets = px.pct_change().iloc[-1]
    prev_month = str(px.index[-2])
    mask = log["signal_month"] == prev_month
    if mask.any():
        held = log.loc[mask, "holdings"].iloc[0].split()
        strat = rets[held].mean()
        spy = rets[BENCHMARK]
        log.loc[mask, ["strategy_return", "spy_return", "excess_return"]] = [
            f"{strat:.4f}", f"{spy:.4f}", f"{strat - spy:.4f}"]

    next_month = str(px.index[-1] + 1)
    new = pd.DataFrame([[month, " ".join(picks), next_month, "", "", ""]], columns=cols)
    log = pd.concat([log, new], ignore_index=True)
    log.to_csv(LOG_FILE, index=False)
    return log


def write_signal(px, ranking, picks, log):
    month = px.index[-1]
    prev = log["holdings"].iloc[-2].split() if len(log) > 1 else []
    buys = [t for t in picks if t not in prev]
    sells = [t for t in prev if t not in picks]

    lines = [f"# Momentum signal for {(month + 1).strftime('%B %Y')}", "",
             f"Based on prices at the {month.strftime('%B %Y')} close.", "",
             "**Hold (one-third each):** " + ", ".join(f"{t} ({NAMES[t]})" for t in picks), ""]
    if prev:
        lines += ["**Changes from last month:** " +
                  (f"sell {', '.join(sells)}; buy {', '.join(buys)}" if buys else "none - keep the same three"), ""]
    lines += ["| Rank | ETF | Sector | 12-month return |", "| --- | --- | --- | --- |"]
    for i, (t, r) in enumerate(ranking.items(), 1):
        lines.append(f"| {i} | {t} | {NAMES[t]} | {r:+.1%} |")

    done = log[log["strategy_return"].fillna("") != ""]
    if len(done):
        s = (1 + done["strategy_return"].astype(float)).prod() - 1
        b = (1 + done["spy_return"].astype(float)).prod() - 1
        lines += ["", f"**Live track record ({len(done)} month{"s" if len(done) != 1 else ""}):** strategy {s:+.1%} vs. SPY {b:+.1%}"]

    lines += ["", "_Educational project, not investment advice._"]
    text = "\n".join(lines) + "\n"
    with open(SIGNAL_FILE, "w") as f:
        f.write(text)
    return text


def main():
    px = load_monthly_prices()
    if len(px) <= LOOKBACK:
        sys.exit("Not enough price history.")
    ranking = rank_sectors(px)
    picks = list(ranking.index[:TOP_N])
    log = update_log(px, picks)
    print(write_signal(px, ranking, picks, log))


if __name__ == "__main__":
    main()
