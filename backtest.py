"""
Backtest of the sector momentum strategy, Feb 2000 to the latest month-end.
Mirrors the Excel model in excel/Sector_Momentum_Backtest.xlsx.

Outputs:
  backtest_results.md  - performance table vs. SPY and an equal-weight mix of the 9 sectors
  backtest_chart.png   - growth of $10,000 and drawdowns
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from momentum import SECTORS, BENCHMARK, LOOKBACK, TOP_N, load_monthly_prices

COST_BPS = 10        # trading cost per $ traded
RISK_FREE = 0.02     # assumed average T-bill yield, for the Sharpe ratio
START = "2000-01"    # first month-end with a full 12-month lookback


def run(px, lookback=LOOKBACK, top_n=TOP_N, cost_bps=COST_BPS):
    rets = px.pct_change()
    mom = px[SECTORS] / px[SECTORS].shift(lookback) - 1
    rank = mom.rank(axis=1, ascending=False, method="first")
    weights = (rank <= top_n).astype(float) / top_n
    weights = weights.loc[START:]
    held = weights.shift(1)                       # picks at month t earn month t+1 (no look-ahead)
    gross = (held * rets[SECTORS].loc[START:]).sum(axis=1).iloc[1:]
    turnover = (held - held.shift(1).fillna(0)).abs().sum(axis=1).iloc[1:]
    return gross - turnover * cost_bps / 10_000


def stats(r):
    growth = (1 + r).cumprod()
    years = len(r) / 12
    vol = r.std() * np.sqrt(12)
    return {
        "Annual return (CAGR)": f"{growth.iloc[-1] ** (1 / years) - 1:.1%}",
        "Volatility": f"{vol:.1%}",
        "Sharpe ratio": f"{(r.mean() * 12 - RISK_FREE) / vol:.2f}",
        "Max drawdown": f"{(growth / growth.cummax() - 1).min():.1%}",
        "$10,000 grows to": f"${10_000 * growth.iloc[-1]:,.0f}",
    }


def main():
    px = load_monthly_prices()
    strat = run(px)
    spy = px[BENCHMARK].pct_change().loc[strat.index]
    ew = px[SECTORS].pct_change().mean(axis=1).loc[strat.index]
    series = {"Strategy": strat, "S&P 500 (SPY)": spy, "Equal-weight sectors": ew}

    table = pd.DataFrame({k: stats(v) for k, v in series.items()})
    period = f"{strat.index[0].strftime('%b %Y')} - {strat.index[-1].strftime('%b %Y')}"
    with open("backtest_results.md", "w") as f:
        f.write(f"## Backtest results ({period})\n\n")
        f.write(table.to_markdown() + "\n")
    print(period)
    print(table)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1]})
    colors = {"Strategy": "#1F3864", "S&P 500 (SPY)": "#A5A5A5", "Equal-weight sectors": "#ED7D31"}
    for name, r in series.items():
        g = 10_000 * (1 + r).cumprod()
        ts = g.index.to_timestamp()
        ax1.plot(ts, g, label=name, color=colors[name], lw=1.8)
        if name != "Equal-weight sectors":
            ax2.plot(ts, g / g.cummax() - 1, color=colors[name], lw=1.4)
    ax1.set_title("Sector momentum strategy: growth of $10,000")
    ax1.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("${x:,.0f}"))
    ax1.legend(frameon=False)
    ax2.set_title("Drawdown from prior peak")
    ax2.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig("backtest_chart.png", dpi=120)


if __name__ == "__main__":
    main()
