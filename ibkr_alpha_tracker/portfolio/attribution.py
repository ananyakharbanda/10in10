"""Day 7 #8 (attribution) + #9 (benchmark sensitivity).

Pure views over data already computed - no refetching. #8 decomposes alpha by
holding period and by position size to show WHERE selection skill sits. #9 shows
how total alpha shifts under alternative benchmark choices, using the non-primary
benchmark rows the engine already produces (e.g. TSM under SOXX instead of QQQ).
"""
import pandas as pd


def _acol(currency):
    return f"alpha_{currency}"


def alpha_by_hold_period(closed_alphas, currency="usd"):
    """Closed-trade alpha bucketed by how long the trade was held."""
    a = _acol(currency)
    df = closed_alphas[closed_alphas["is_primary"]].copy()
    days = (pd.to_datetime(df["exit_date"]) - pd.to_datetime(df["entry_date"])).dt.days
    bins = [-1, 7, 30, 90, 10 ** 9]
    labels = ["<1wk", "1wk-1mo", "1-3mo", ">3mo"]
    df["bucket"] = pd.cut(days, bins=bins, labels=labels)
    out = df.groupby("bucket", observed=True)[a].agg(["sum", "count"]).reset_index()
    return out.rename(columns={"sum": "alpha", "count": "n"})


def alpha_by_size(closed_alphas, currency="usd"):
    """Closed-trade alpha bucketed by capital deployed (small/medium/large terciles)."""
    a = _acol(currency)
    df = closed_alphas[closed_alphas["is_primary"]].copy()
    cap = (df["entry_price"] * df["quantity"]).abs()
    try:
        df["bucket"] = pd.qcut(cap, 3, labels=["small", "medium", "large"], duplicates="drop")
    except ValueError:
        df["bucket"] = "all"
    out = df.groupby("bucket", observed=True)[a].agg(["sum", "count"]).reset_index()
    return out.rename(columns={"sum": "alpha", "count": "n"})


def benchmark_sensitivity(all_alphas, currency="usd"):
    """Total realized alpha under each benchmark, for tickers that have more than
    one candidate. Uses the non-primary rows the engine already emits."""
    a = _acol(currency)
    rows = []
    for ticker, grp in all_alphas.groupby("ticker"):
        if grp["benchmark"].nunique() < 2:
            continue
        for bench, bg in grp.groupby("benchmark"):
            rows.append({"ticker": ticker, "benchmark": bench,
                         "alpha": round(bg[a].sum(), 2),
                         "primary": bool(bg["is_primary"].iloc[0])})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config
    from data.ibkr_client import fetch_flex_report
    from data.parser import parse_trades, filter_stock_trades
    from data.ledger import merge_trades
    from data.benchmark import get_benchmark_prices
    from portfolio.matching import match_round_trips
    from portfolio.counterfactual import compute_all_trade_alphas
    from app.dashboard import load_benchmarks

    bmap, dflt, yf = load_benchmarks()
    trades = merge_trades(filter_stock_trades(parse_trades(
        fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID))))
    closed, _, _ = match_round_trips(trades)
    start = closed["entry_date"].min(); end = pd.Timestamp.today()
    distinct = {b for bs in bmap.values() for b in bs} | {dflt}
    series = {b: get_benchmark_prices(b, start, end) for b in distinct}
    usdsgd = get_benchmark_prices("USDSGD=X", start, end)
    alphas = compute_all_trade_alphas(closed, bmap, series, usdsgd, default_benchmark=dflt)

    print("By holding period:\n", alpha_by_hold_period(alphas).to_string(index=False))
    print("\nBy size:\n", alpha_by_size(alphas).to_string(index=False))
    print("\nBenchmark sensitivity:\n", benchmark_sensitivity(alphas).to_string(index=False))
