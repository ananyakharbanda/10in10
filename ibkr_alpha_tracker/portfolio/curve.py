import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from data.benchmark import price_on


def build_daily_alpha(trades_df, stock_prices, benchmark_prices, usdsgd_prices,
                      currency="usd"):
    """Reconstruct a daily alpha-return series for the whole portfolio.

    Logic: each day, value your book (shares held x price) and a benchmark
    book where every dollar you deployed bought the benchmark instead.
    Daily alpha return = your daily return - benchmark daily return.
    Returns a DataFrame indexed by date with cumulative columns."""
    trades = trades_df.sort_values("datetime").copy()
    start = trades["datetime"].min().normalize()
    end = pd.Timestamp.today().normalize()
    days = pd.date_range(start, end, freq="D")

    tickers = trades["ticker"].unique()

    # --- 1. Daily share holdings per ticker (cumulative signed quantity) ---
    holdings = pd.DataFrame(0.0, index=days, columns=tickers)
    for _, t in trades.iterrows():
        d = t["datetime"].normalize()
        holdings.loc[holdings.index >= d, t["ticker"]] += t["quantity"]

    # --- 2. Your portfolio value each day, in chosen currency ---
    def fx_on(day):  # native USD -> chosen currency multiplier
        rate = price_on(usdsgd_prices, day)
        return 1.0 if currency == "usd" else rate

    your_value = pd.Series(0.0, index=days)
    for tk in tickers:
        px = pd.Series([price_on(stock_prices[tk], d) for d in days], index=days)
        your_value += holdings[tk] * px
    your_value *= pd.Series([fx_on(d) for d in days], index=days)

    # --- 3. Benchmark book: each cash inflow buys the benchmark instead ---
    # Cash deployed on a day = sum of (quantity * entry_price) for buys that day.
    bench_units = pd.Series(0.0, index=days)   # cumulative benchmark "shares"
    for _, t in trades.iterrows():
        if t["quantity"] <= 0:
            continue  # only buys deploy new capital
        d = t["datetime"].normalize()
        capital_usd = t["quantity"] * t["price"]   # native; USD here (stocks are USD)
        bench_px = price_on(benchmark_prices, d)
        bench_units.loc[bench_units.index >= d] += capital_usd / bench_px
    bench_px_daily = pd.Series([price_on(benchmark_prices, d) for d in days], index=days)
    bench_value = bench_units * bench_px_daily
    bench_value *= pd.Series([fx_on(d) for d in days], index=days)

    # --- 4. Daily returns, then alpha return = yours - benchmark's ---
    df = pd.DataFrame({"your_value": your_value, "bench_value": bench_value})
    df = df[df["your_value"] > 0]   # drop pre-first-trade days
    df["your_ret"] = df["your_value"].pct_change()
    df["bench_ret"] = df["bench_value"].pct_change()
    df["alpha_ret"] = df["your_ret"] - df["bench_ret"]
    df["cum_alpha_ret"] = (1 + df["alpha_ret"].fillna(0)).cumprod() - 1
    df["cum_alpha_dollars"] = df["your_value"] - df["bench_value"]
    return df


def alpha_sharpe(alpha_returns, periods=252):
    """Annualized Sharpe on the alpha-return series. mean/std * sqrt(252)."""
    r = alpha_returns.dropna()
    if r.std() == 0 or len(r) < 2:
        return float("nan")
    return r.mean() / r.std() * np.sqrt(periods)


def alpha_sortino(alpha_returns, periods=252):
    """Like Sharpe but denominator is downside (negative-day) deviation only."""
    r = alpha_returns.dropna()
    downside = r[r < 0]
    if len(downside) < 2 or downside.std() == 0:
        return float("nan")
    return r.mean() / downside.std() * np.sqrt(periods)


def alpha_max_drawdown(cum_alpha_dollars):
    """Worst peak-to-trough on the cumulative dollar-alpha curve.
    Returns (max_drawdown_dollars, peak_date, trough_date)."""
    s = cum_alpha_dollars
    running_peak = s.cummax()
    drawdown = s - running_peak           # <= 0
    trough_date = drawdown.idxmin()
    max_dd = drawdown.min()
    peak_date = s.loc[:trough_date].idxmax()
    return abs(max_dd), peak_date, trough_date


if __name__ == "__main__":
    import config
    from data.ibkr_client import fetch_flex_report
    from data.parser import parse_trades, filter_stock_trades
    from data.benchmark import get_benchmark_prices

    trades = filter_stock_trades(parse_trades(
        fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)))

    start = trades["datetime"].min()
    end = pd.Timestamp.today()
    tickers = trades["ticker"].unique()
    stock_prices = {t: get_benchmark_prices(t, start, end) for t in tickers}
    qqq = get_benchmark_prices("QQQ", start, end)
    usdsgd = get_benchmark_prices("USDSGD=X", start, end)

    for ccy in ("usd", "sgd"):
        df = build_daily_alpha(trades, stock_prices, qqq, usdsgd, currency=ccy)
        dd, peak, trough = alpha_max_drawdown(df["cum_alpha_dollars"])
        print(f"\n=== Daily alpha series ({ccy.upper()}) — {len(df)} trading days ===")
        print(f"  Alpha Sharpe       : {alpha_sharpe(df['alpha_ret']):.2f}")
        print(f"  Alpha Sortino      : {alpha_sortino(df['alpha_ret']):.2f}")
        print(f"  Max alpha drawdown : {dd:,.2f} {ccy.upper()} "
              f"(peak {peak.date()} -> trough {trough.date()})")
        print(f"  Final cum alpha    : {df['cum_alpha_dollars'].iloc[-1]:,.2f} {ccy.upper()}")
        print(df[["your_value", "bench_value", "alpha_ret", "cum_alpha_dollars"]]
              .iloc[::20].to_string())   # every 20th day to keep it readable
