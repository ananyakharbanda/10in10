"""Day 7 #6 (part 2) - account-level time-weighted return (TWR).

TWR answers a different question from per-trade alpha: how did the WHOLE account
do - cash drag included - versus being fully invested in the benchmark? It
neutralises the timing of deposits/withdrawals so the figure reflects investment
decisions, not when money was added.

Daily method: split the timeline at each external flow and chain-link the
sub-period returns. With a flow F_t on day t (start-of-day convention):
    r_t = NAV_t / (NAV_{t-1} + F_t) - 1
    TWR = product(1 + r_t) - 1
"""
import numpy as np
import pandas as pd


def time_weighted_return(nav, flows):
    """nav: date-indexed Series of NAV (base ccy). flows: date-indexed Series of
    net external flow per day (base ccy; deposits +, withdrawals -). Returns the
    cumulative TWR as a fraction (0.10 = +10%), or nan if insufficient data."""
    nav = nav.sort_index().astype(float)
    if len(nav) < 2:
        return float("nan")
    flows = flows.reindex(nav.index).fillna(0.0) if len(flows) else pd.Series(0.0, index=nav.index)

    growth = 1.0
    prev = nav.iloc[0]
    for i in range(1, len(nav)):
        opening = prev + flows.iloc[i]          # capital available for the day
        cur = nav.iloc[i]
        if opening > 0:
            growth *= cur / opening
        prev = cur
    return growth - 1.0


def benchmark_twr(price_series, start, end):
    """Buy-and-hold price return of a benchmark over [start, end] (a fraction).
    Pass a price series already in the same currency as the NAV for a fair
    comparison (e.g. QQQ close * USDSGD for an SGD-base account)."""
    s = price_series.sort_index()
    s = s[(s.index >= pd.Timestamp(start)) & (s.index <= pd.Timestamp(end))]
    if len(s) < 2 or s.iloc[0] == 0:
        return float("nan")
    return s.iloc[-1] / s.iloc[0] - 1.0


def build_twr_from_nav_summary(nav_summary, benchmark_price_base):
    """Account TWR (read from IBKR's ChangeInNAV) vs the benchmark's return over
    the same window. benchmark_price_base must be in the account base currency.
    Returns a dict for the payload, or None if the summary/TWR is missing.

    Note: TWR neutralises deposit timing, so it's directly comparable to a
    buy-and-hold index return over the same window - and any shortfall partly
    reflects cash drag (periods the account sat in cash while the index rose),
    which is exactly what an account-level view is meant to reveal."""
    if not nav_summary or nav_summary.get("ibkr_twr_pct") is None:
        return None
    start, end = nav_summary["from_date"], nav_summary["to_date"]
    acct = nav_summary["ibkr_twr_pct"]                 # already a percent
    bench = benchmark_twr(benchmark_price_base, start, end)
    bench_pct = None if pd.isna(bench) else round(bench * 100, 2)
    excess = None if bench_pct is None else round(acct - bench_pct, 2)
    return {
        "account_twr_pct": round(acct, 2),
        "benchmark_twr_pct": bench_pct,
        "excess_pct": excess,
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
        "n_days": int((end - start).days),
        "source": "IBKR ChangeInNAV",
    }


def build_twr_summary(nav, flows, benchmark_price_base):
    """Account TWR vs benchmark over the NAV window. benchmark_price_base must be
    in the account base currency. Returns a dict ready for the payload, or None
    if NAV data is unavailable."""
    nav = nav.sort_index().astype(float)
    if len(nav) < 2:
        return None
    start, end = nav.index.min(), nav.index.max()
    acct = time_weighted_return(nav, flows)
    bench = benchmark_twr(benchmark_price_base, start, end)
    excess = (acct - bench) if (pd.notna(acct) and pd.notna(bench)) else float("nan")
    return {
        "account_twr_pct": None if pd.isna(acct) else round(acct * 100, 2),
        "benchmark_twr_pct": None if pd.isna(bench) else round(bench * 100, 2),
        "excess_pct": None if pd.isna(excess) else round(excess * 100, 2),
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
        "n_days": int(len(nav)),
    }


if __name__ == "__main__":
    # synthetic sanity check: a deposit mid-way must NOT distort TWR.
    idx = pd.date_range("2026-01-01", periods=5, freq="D")
    # day-by-day the account grows 1% per day; a +1000 deposit lands on day 3.
    nav = pd.Series([1000, 1010, 2030.1, 2050.401, 2070.905], index=idx)
    flows = pd.Series([0, 0, 1000, 0, 0], index=idx)
    twr = time_weighted_return(nav, flows)
    print(f"TWR with mid-period deposit: {twr*100:.4f}%  (expect ~4.06% = 1.01^4-1)")
    assert abs(twr - (1.01 ** 4 - 1)) < 1e-6, "deposit timing leaked into TWR!"
    print("PASS - deposit timing correctly neutralised.")
