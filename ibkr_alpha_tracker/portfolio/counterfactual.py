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

    # Your P&L: convert each cashflow at ITS OWN date's rate. The entry/exit
    # rates differing is what captures currency drift over the holding period.
    your_pnl_usd = native_exit_value * ntu_exit - native_capital * ntu_entry
    your_pnl_sgd = native_exit_value * nts_exit - native_capital * nts_entry

    # Counterfactual: same entry capital into QQQ (a USD-denominated asset).
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
        "your_pnl_usd": your_pnl_usd, "your_pnl_sgd": your_pnl_sgd,
        "benchmark_pnl_usd": benchmark_pnl_usd, "benchmark_pnl_sgd": benchmark_pnl_sgd,
        "alpha_usd": your_pnl_usd - benchmark_pnl_usd,
        "alpha_sgd": your_pnl_sgd - benchmark_pnl_sgd,
    }


def compute_all_trade_alphas(closed_df, benchmark_prices, usdsgd_prices):
    """Map compute_trade_alpha over all closed trips -> a DataFrame."""
    rows = [compute_trade_alpha(t, benchmark_prices, usdsgd_prices)
            for _, t in closed_df.iterrows()]
    df = pd.DataFrame(rows)
    df["alpha_per_day_usd"] = df["alpha_usd"] / df["hold_days"]
    df["alpha_per_day_sgd"] = df["alpha_sgd"] / df["hold_days"]
    return df

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config
    from data.ibkr_client import fetch_flex_report
    from data.parser import parse_trades, filter_stock_trades
    from data.benchmark import get_benchmark_prices
    from portfolio.matching import match_round_trips

    trades = filter_stock_trades(parse_trades(
        fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)))
    closed, _ = match_round_trips(trades)

    start, end = closed["entry_date"].min(), pd.Timestamp.today()
    qqq = get_benchmark_prices("QQQ", start, end)
    usdsgd = get_benchmark_prices("USDSGD=X", start, end)

    alphas = compute_all_trade_alphas(closed, qqq, usdsgd)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print(alphas[["ticker", "quantity", "hold_days", "benchmark_return",
                  "your_pnl_usd", "benchmark_pnl_usd", "alpha_usd", "alpha_sgd"]]
          .to_string(index=False))
    print(f"\nTotal alpha USD: {alphas['alpha_usd'].sum():,.2f}")
    print(f"Total alpha SGD: {alphas['alpha_sgd'].sum():,.2f}")
