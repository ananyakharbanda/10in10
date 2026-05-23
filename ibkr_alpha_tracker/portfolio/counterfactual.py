import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from data.benchmark import price_on


def compute_trade_alpha(trip, benchmark_prices, usdsgd_prices):
    """One closed trip's alpha vs the benchmark, in BOTH USD and SGD.

    `trip` is a row from match_round_trips (ticker, quantity, entry/exit
    date+price+fx, currency). Returns a dict of computed columns.
    """
    native = trip["currency"]
    qty = trip["quantity"]

    # Your cashflows, in the trip's native currency (gross, pre-commission).
    native_capital = qty * trip["entry_price"]      # what you put in
    native_exit_value = qty * trip["exit_price"]    # what you got back

    # Benchmark return over the hold - a pure ratio, no currency attached.
    bench_entry = price_on(benchmark_prices, trip["entry_date"])
    bench_exit = price_on(benchmark_prices, trip["exit_date"])
    benchmark_return = (bench_exit - bench_entry) / bench_entry

    # USD<->SGD rate per date. For USD trips we reuse IBKR's own fx (which IS
    # USD->SGD), so your side and the benchmark side share one rate source;
    # otherwise we use the Yahoo USDSGD series.
    if native == "USD":
        usdsgd_entry, usdsgd_exit = trip["entry_fx"], trip["exit_fx"]
    else:
        usdsgd_entry = price_on(usdsgd_prices, trip["entry_date"])
        usdsgd_exit = price_on(usdsgd_prices, trip["exit_date"])

    # native -> SGD  (identity if already SGD, else IBKR's trade-time fx)
    nts_entry = 1.0 if native == "SGD" else trip["entry_fx"]
    nts_exit = 1.0 if native == "SGD" else trip["exit_fx"]
    # native -> USD  (identity if already USD, else bridge via SGD)
    ntu_entry = 1.0 if native == "USD" else nts_entry / usdsgd_entry
    ntu_exit = 1.0 if native == "USD" else nts_exit / usdsgd_exit

    # Your GROSS P&L: convert each cashflow at ITS OWN date's rate. The entry/
    # exit rates differing is what captures currency drift over the holding period.
    gross_pnl_usd = native_exit_value * ntu_exit - native_capital * ntu_entry
    gross_pnl_sgd = native_exit_value * nts_exit - native_capital * nts_entry

    # Commissions (native, IBKR sign: negative = a cost), apportioned per trip by
    # the matcher. Each leg converts at its own date's rate. Charged to YOUR side
    # only; the benchmark is treated as the idealized frictionless passive
    # alternative (the conservative choice - it also rewards passive investing for
    # transacting less). Open lots carry entry_commission with exit_commission 0.
    entry_comm = trip.get("entry_commission", 0.0) or 0.0
    exit_comm = trip.get("exit_commission", 0.0) or 0.0
    commission_usd = entry_comm * ntu_entry + exit_comm * ntu_exit
    commission_sgd = entry_comm * nts_entry + exit_comm * nts_exit

    # Your NET P&L (commission is negative, so this reduces gross).
    your_pnl_usd = gross_pnl_usd + commission_usd
    your_pnl_sgd = gross_pnl_sgd + commission_sgd

    # Counterfactual: same entry capital into the benchmark (USD-denominated).
    capital_usd = native_capital * ntu_entry
    bench_value_usd = capital_usd * (1 + benchmark_return)
    benchmark_pnl_usd = bench_value_usd - capital_usd
    # In SGD: the USD position converted at entry vs exit rates (drift again).
    benchmark_pnl_sgd = bench_value_usd * usdsgd_exit - capital_usd * usdsgd_entry

    hold_days = (pd.Timestamp(trip["exit_date"]) - pd.Timestamp(trip["entry_date"])).days or 1

    return {
        "ticker": trip["ticker"], "quantity": qty, "currency": native,
        "entry_date": trip["entry_date"], "exit_date": trip["exit_date"],
        "hold_days": hold_days, "benchmark_return": benchmark_return,
        # Your own gross price return in native currency (a ratio, so it pairs
        # directly against benchmark_return on the scatter). Exposed here so the
        # chart layer never has to recompute it.
        "your_return": (native_exit_value - native_capital) / native_capital,
        # Current market value of the position in each currency (for the
        # open-position case this is qty x mark; used to size the treemap).
        "exit_value_usd": native_exit_value * ntu_exit,
        "exit_value_sgd": native_exit_value * nts_exit,
        # NET of your commissions; gross and commission exposed for transparency.
        "your_pnl_usd": your_pnl_usd, "your_pnl_sgd": your_pnl_sgd,
        "gross_pnl_usd": gross_pnl_usd, "gross_pnl_sgd": gross_pnl_sgd,
        "commission_usd": commission_usd, "commission_sgd": commission_sgd,
        "benchmark_pnl_usd": benchmark_pnl_usd, "benchmark_pnl_sgd": benchmark_pnl_sgd,
        "alpha_usd": your_pnl_usd - benchmark_pnl_usd,
        "alpha_sgd": your_pnl_sgd - benchmark_pnl_sgd,
    }


def compute_all_trade_alphas(closed_df, benchmark_map, series_by_ticker,
                             usdsgd_prices, default_benchmark="QQQ"):
    """benchmark_map: {your_ticker -> [benchmark_ticker, ...]}.
    A holding can list several benchmarks (e.g. TSM -> QQQ and SOXX).
    Produces long format: one row per (trip, benchmark)."""
    rows = []
    for _, t in closed_df.iterrows():
        benches = benchmark_map.get(t["ticker"], [default_benchmark])
        for i, bench_ticker in enumerate(benches):
            row = compute_trade_alpha(t, series_by_ticker[bench_ticker], usdsgd_prices)
            row["benchmark"] = bench_ticker
            row["is_primary"] = (i == 0)   # first listed = primary, for totals
            rows.append(row)
    df = pd.DataFrame(rows)
    df["alpha_per_day_usd"] = df["alpha_usd"] / df["hold_days"]
    df["alpha_per_day_sgd"] = df["alpha_sgd"] / df["hold_days"]
    return df


if __name__ == "__main__":
    import config
    from data.ibkr_client import fetch_flex_report
    from data.parser import parse_trades, filter_stock_trades
    from data.benchmark import get_benchmark_prices
    from portfolio.matching import match_round_trips

    trades = filter_stock_trades(parse_trades(
        fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)))
    closed, _, _ = match_round_trips(trades)

    BENCHMARK_MAP = {
        "NVDA": ["QQQ"], "MSFT": ["QQQ"], "GOOG": ["QQQ"], "AMZN": ["QQQ"],
        "QQQ": ["QQQ"], "TSM": ["QQQ", "SOXX"], "MC": ["FEZ"],
    }

    start, end = closed["entry_date"].min(), pd.Timestamp.today()
    distinct = {b for benches in BENCHMARK_MAP.values() for b in benches}
    series_by_ticker = {bt: get_benchmark_prices(bt, start, end) for bt in distinct}
    usdsgd = get_benchmark_prices("USDSGD=X", start, end)

    alphas = compute_all_trade_alphas(closed, BENCHMARK_MAP, series_by_ticker, usdsgd)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print(alphas[["ticker", "benchmark", "quantity", "hold_days",
                  "benchmark_return", "your_return", "alpha_usd", "alpha_sgd"]].to_string(index=False))
    primary = alphas[alphas["is_primary"]]
    print(f"\nTotal alpha (primary benchmarks)  USD: {primary['alpha_usd'].sum():,.2f}")
    print(f"Total alpha (primary benchmarks)  SGD: {primary['alpha_sgd'].sum():,.2f}")
