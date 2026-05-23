import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from data.benchmark import price_on


def _primary_benchmark(ticker, benchmark_map, default="QQQ"):
    return benchmark_map.get(ticker, [default])[0]


def build_daily_alpha(closed, open_lots, benchmark_map, stock_prices,
                      series_by_ticker, fx_to_usd, usdsgd_prices,
                      currency="usd", default_benchmark="QQQ"):
    """Cash-correct daily portfolio-vs-benchmark alpha.

    Each lot (open or closed) is valued every day on BOTH sides, in USD:
      - your side : shares x daily price (native) -> USD, while open;
                    banked exit proceeds (USD) once closed.
      - bench side: matched USD capital grown by the benchmark while open;
                    redeemed (banked) at the exit-date benchmark level once closed.
    A close converts BOTH sides to a static banked value, so neither book loses
    the proceeds -> the comparison stays fair through every sell (no cliff).

    Deposits/withdrawals don't appear by design: alpha comes only from deployed
    capital; idle cash has no benchmark counterfactual.

    fx_to_usd: {currency -> daily Series of native->USD}. USD is identity.
    """
    legs = []
    for _, t in closed.iterrows():
        legs.append((t["ticker"], t["quantity"], t["currency"], t["entry_date"],
                     t["entry_price"], t["exit_date"], t["exit_price"],
                     t.get("entry_commission", 0.0), t.get("exit_commission", 0.0)))
    for _, t in open_lots.iterrows():
        legs.append((t["ticker"], t["quantity"], t["currency"], t["entry_date"],
                     t["entry_price"], None, None,
                     t.get("entry_commission", 0.0), 0.0))
    if not legs:
        return pd.DataFrame()

    start = min(pd.Timestamp(l[3]).normalize() for l in legs)
    end = pd.Timestamp.today().normalize()
    days = pd.date_range(start, end, freq="D")

    # --- precompute daily series so we don't call price_on in the inner loop ---
    def daily(series):
        return pd.Series([price_on(series, d) for d in days], index=days)

    tickers = {l[0] for l in legs}
    stock_daily = {tk: daily(stock_prices[tk]) for tk in tickers}

    benches = {_primary_benchmark(tk, benchmark_map, default_benchmark) for tk in tickers}
    bench_daily = {bt: daily(series_by_ticker[bt]) for bt in benches}

    currencies = {l[2] for l in legs}
    fxu_daily = {c: (pd.Series(1.0, index=days) if c == "USD" else daily(fx_to_usd[c]))
                 for c in currencies}

    your_value = pd.Series(0.0, index=days)
    bench_value = pd.Series(0.0, index=days)

    for ticker, qty, native, e_date, e_price, x_date, x_price, e_comm, x_comm in legs:
        e = pd.Timestamp(e_date).normalize()
        bt = _primary_benchmark(ticker, benchmark_map, default_benchmark)

        # Capital deployed by this lot, in USD (bridge native -> USD at entry).
        fxu_entry = fxu_daily[native].asof(e)
        capital_usd = qty * e_price * fxu_entry
        bench_units = capital_usd / price_on(series_by_ticker[bt], e)

        x = pd.Timestamp(x_date).normalize() if x_date is not None else None
        open_mask = (days >= e) if x is None else ((days >= e) & (days < x))
        idx_open = days[open_mask]

        # Open period: mark both sides to market (your side bridged to USD).
        your_value.loc[idx_open] += qty * stock_daily[ticker].loc[idx_open] * fxu_daily[native].loc[idx_open]
        bench_value.loc[idx_open] += bench_units * bench_daily[bt].loc[idx_open]

        # Commissions hit YOUR side only (benchmark is frictionless): the entry
        # commission from entry onward, the exit commission from exit onward.
        # They're negative, so they shift your_value down by a constant.
        your_value.loc[days[days >= e]] += e_comm * fxu_entry

        # Closed period: both sides banked at the exit (static thereafter).
        if x is not None:
            idx_closed = days[days >= x]
            your_value.loc[idx_closed] += qty * x_price * fxu_daily[native].asof(x)
            bench_value.loc[idx_closed] += bench_units * price_on(series_by_ticker[bt], x)
            your_value.loc[idx_closed] += x_comm * fxu_daily[native].asof(x)

    # Express the whole book in the chosen display currency.
    if currency == "sgd":
        fx = daily(usdsgd_prices)
        your_value, bench_value = your_value * fx, bench_value * fx

    df = pd.DataFrame({"your_value": your_value, "bench_value": bench_value})
    df = df[df["your_value"] > 0]
    df["your_ret"] = df["your_value"].pct_change()
    df["bench_ret"] = df["bench_value"].pct_change()
    df["alpha_ret"] = df["your_ret"] - df["bench_ret"]
    df["cum_alpha_dollars"] = df["your_value"] - df["bench_value"]
    return df


def alpha_sharpe(alpha_returns, periods=252):
    r = alpha_returns.dropna()
    if len(r) < 2 or r.std() == 0:
        return float("nan")
    return r.mean() / r.std() * np.sqrt(periods)


def alpha_sortino(alpha_returns, periods=252):
    r = alpha_returns.dropna()
    downside = r[r < 0]
    if len(downside) < 2 or downside.std() == 0:
        return float("nan")
    return r.mean() / downside.std() * np.sqrt(periods)


def alpha_max_drawdown(cum_alpha_dollars):
    s = cum_alpha_dollars
    peak = s.cummax()
    dd = s - peak
    trough = dd.idxmin()
    return abs(dd.min()), s.loc[:trough].idxmax(), trough


if __name__ == "__main__":
    import config
    from data.ibkr_client import fetch_flex_report
    from data.parser import parse_trades, filter_stock_trades
    from data.benchmark import get_benchmark_prices
    from portfolio.matching import match_round_trips

    trades = filter_stock_trades(parse_trades(
        fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)))
    closed, open_lots = match_round_trips(trades)

    BENCHMARK_MAP = {
        "NVDA": ["QQQ"], "MSFT": ["QQQ"], "GOOG": ["QQQ"], "AMZN": ["QQQ"],
        "QQQ": ["QQQ"], "TSM": ["QQQ", "SOXX"], "MC": ["FEZ"],
    }
    # Your ticker -> the yfinance symbol for ITS OWN price (LVMH = MC.PA, not US "MC").
    YF_SYMBOL = {"MC": "MC.PA"}

    start = pd.concat([closed["entry_date"], open_lots["entry_date"]]).min()
    end = pd.Timestamp.today()

    all_tickers = pd.concat([closed["ticker"], open_lots["ticker"]]).unique()
    stock_prices = {tk: get_benchmark_prices(YF_SYMBOL.get(tk, tk), start, end)
                    for tk in all_tickers}

    distinct_benches = {b for benches in BENCHMARK_MAP.values() for b in benches}
    series_by_ticker = {bt: get_benchmark_prices(bt, start, end) for bt in distinct_benches}

    usdsgd = get_benchmark_prices("USDSGD=X", start, end)
    # native->USD series for any non-USD currency you hold (EUR here, for LVMH).
    fx_to_usd = {"EUR": get_benchmark_prices("EURUSD=X", start, end)}

    for ccy in ("usd", "sgd"):
        df = build_daily_alpha(closed, open_lots, BENCHMARK_MAP, stock_prices,
                               series_by_ticker, fx_to_usd, usdsgd, currency=ccy)
        dd, peak, trough = alpha_max_drawdown(df["cum_alpha_dollars"])
        print(f"\n=== Daily alpha ({ccy.upper()}) — {len(df)} trading days ===")
        print(f"  Alpha Sharpe       : {alpha_sharpe(df['alpha_ret']):.2f}")
        print(f"  Alpha Sortino      : {alpha_sortino(df['alpha_ret']):.2f}")
        print(f"  Max alpha drawdown : {dd:,.2f} {ccy.upper()} "
              f"(peak {peak.date()} -> trough {trough.date()})")
        print(f"  Final cum alpha    : {df['cum_alpha_dollars'].iloc[-1]:,.2f} {ccy.upper()}")
        print(df[["your_value", "bench_value", "alpha_ret", "cum_alpha_dollars"]]
              .iloc[::25].to_string())
