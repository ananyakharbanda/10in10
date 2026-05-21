import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from data.benchmark import price_on
from portfolio.counterfactual import compute_trade_alpha


def value_open_lots(open_df, benchmark_map, series_by_ticker, usdsgd_prices,
                    stock_prices_by_ticker, as_of=None, default_benchmark="QQQ"):
    """Live (unrealized) alpha for each open lot, marked to `as_of` (today).

    The trick: an open lot is just a trip that 'closes' today at the current
    market price. We build that synthetic trip and reuse compute_trade_alpha,
    so all the dual-currency / FX-drift logic is shared with closed trades.
    Produces one row per (lot, benchmark)."""
    as_of = pd.Timestamp(as_of or pd.Timestamp.today()).normalize()
    usdsgd_today = price_on(usdsgd_prices, as_of)

    rows = []
    for _, lot in open_df.iterrows():
        ticker = lot["ticker"]
        native = lot["currency"]

        # Today's price of YOUR stock (not the benchmark) = the current mark.
        mark = price_on(stock_prices_by_ticker[ticker], as_of)

        # Today's native->SGD rate, to value the position as of now.
        if native == "USD":
            exit_fx = usdsgd_today
        elif native == "SGD":
            exit_fx = 1.0
        else:
            # No live native->SGD series on hand. Only matters for open
            # NON-USD positions, of which there are currently none.
            # Refine in Day 6 if you hold foreign stocks open.
            exit_fx = lot["entry_fx"]

        # An open lot, dressed up as a trip that closes today at the mark.
        synth = {
            "ticker": ticker,
            "quantity": lot["quantity"],
            "currency": native,
            "entry_date": lot["entry_date"],
            "entry_price": lot["entry_price"],
            "entry_fx": lot["entry_fx"],
            "exit_date": as_of,
            "exit_price": mark,
            "exit_fx": exit_fx,
        }

        benches = benchmark_map.get(ticker, [default_benchmark])
        for i, bench_ticker in enumerate(benches):
            row = compute_trade_alpha(synth, series_by_ticker[bench_ticker], usdsgd_prices)
            row["benchmark"] = bench_ticker
            row["is_primary"] = (i == 0)
            row["entry_price"] = lot["entry_price"]
            row["mark_price"] = mark
            row["status"] = "OPEN"
            rows.append(row)

    cols_order = ["ticker", "benchmark", "status", "quantity", "entry_date",
                  "entry_price", "mark_price", "hold_days", "benchmark_return",
                  "your_pnl_usd", "your_pnl_sgd", "alpha_usd", "alpha_sgd",
                  "is_primary"]
    df = pd.DataFrame(rows)
    return df[cols_order] if not df.empty else df


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

    start = open_lots["entry_date"].min()
    end = pd.Timestamp.today()

    # Fetch each distinct benchmark once...
    distinct_benches = {b for benches in BENCHMARK_MAP.values() for b in benches}
    series_by_ticker = {bt: get_benchmark_prices(bt, start, end) for bt in distinct_benches}
    usdsgd = get_benchmark_prices("USDSGD=X", start, end)

    # ...and today's price for each of YOUR open holdings (ticker-agnostic fetch).
    open_tickers = open_lots["ticker"].unique()
    stock_prices = {t: get_benchmark_prices(t, start, end) for t in open_tickers}

    live = value_open_lots(open_lots, BENCHMARK_MAP, series_by_ticker, usdsgd, stock_prices)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    print(live.to_string(index=False))

    primary = live[live["is_primary"]]
    print(f"\nTotal UNREALIZED alpha (primary)  USD: {primary['alpha_usd'].sum():,.2f}")
    print(f"Total UNREALIZED alpha (primary)  SGD: {primary['alpha_sgd'].sum():,.2f}")
