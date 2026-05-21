import pandas as pd


def win_rate(alpha_series):
    """Fraction of trades that beat their benchmark (alpha > 0)."""
    n = len(alpha_series)
    if n == 0:
        return float("nan")
    return (alpha_series > 0).sum() / n


def profit_factor(alpha_series):
    """Gross positive alpha / gross negative alpha (absolute).
    Above 1 means your winners outweigh your losers; >1.5 is solid.
    Infinite if there are no losing trades."""
    wins = alpha_series[alpha_series > 0].sum()
    losses = alpha_series[alpha_series < 0].sum()   # negative number
    if losses == 0:
        return float("inf") if wins > 0 else float("nan")
    return wins / abs(losses)


def avg_win_vs_loss(alpha_series):
    """Average winning alpha and average losing alpha, plus their ratio.
    The ratio matters more than either alone: a 2:1 ratio means your
    typical win is twice your typical loss."""
    wins = alpha_series[alpha_series > 0]
    losses = alpha_series[alpha_series < 0]
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = losses.mean() if len(losses) else 0.0   # negative
    ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else float("inf")
    return {"avg_win": avg_win, "avg_loss": avg_loss, "win_loss_ratio": ratio}


def trade_summary(alphas_df, currency="usd"):
    """Run all trade-level metrics on one currency's alpha column.
    Uses only primary-benchmark rows so multi-benchmark trades aren't
    double-counted."""
    col = f"alpha_{currency}"
    primary = alphas_df[alphas_df["is_primary"]]
    s = primary[col]
    avg = avg_win_vs_loss(s)
    return {
        "currency": currency.upper(),
        "n_trades": len(s),
        "win_rate": win_rate(s),
        "profit_factor": profit_factor(s),
        "avg_win": avg["avg_win"],
        "avg_loss": avg["avg_loss"],
        "win_loss_ratio": avg["win_loss_ratio"],
        "total_alpha": s.sum(),
    }

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config
    from data.ibkr_client import fetch_flex_report
    from data.parser import parse_trades, filter_stock_trades
    from data.benchmark import get_benchmark_prices
    from portfolio.matching import match_round_trips
    from portfolio.counterfactual import compute_all_trade_alphas

    trades = filter_stock_trades(parse_trades(
        fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)))
    closed, _ = match_round_trips(trades)

    BENCHMARK_MAP = {
        "NVDA": ["QQQ"], "MSFT": ["QQQ"], "GOOG": ["QQQ"], "AMZN": ["QQQ"],
        "QQQ": ["QQQ"], "TSM": ["QQQ", "SOXX"], "MC": ["FEZ"],
    }
    start, end = closed["entry_date"].min(), pd.Timestamp.today()
    distinct = {b for benches in BENCHMARK_MAP.values() for b in benches}
    series = {bt: get_benchmark_prices(bt, start, end) for bt in distinct}
    usdsgd = get_benchmark_prices("USDSGD=X", start, end)
    alphas = compute_all_trade_alphas(closed, BENCHMARK_MAP, series, usdsgd)

    for ccy in ("usd", "sgd"):
        print(f"\n=== Trade-level metrics ({ccy.upper()}) ===")
        for k, v in trade_summary(alphas, ccy).items():
            print(f"  {k:16} {v}")
