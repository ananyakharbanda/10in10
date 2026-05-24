"""Live data layer: run the whole pipeline fresh and return one JSON-ready
payload (metrics + the six Plotly figures + trades + positions). The API calls
this on every request, so the page always reflects the portfolio as of now."""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.io as pio

import config
from data.ibkr_client import fetch_flex_report
from data.parser import parse_trades, filter_stock_trades
from data.ledger import merge_trades
from data.cash import parse_cash_transactions, external_flows_by_day, parse_change_in_nav
from data.benchmark import get_benchmark_prices
from portfolio.matching import match_round_trips
from portfolio.counterfactual import compute_all_trade_alphas
from portfolio.positions import value_open_lots
from portfolio.curve import (build_daily_alpha, alpha_sharpe, alpha_sortino,
                             alpha_max_drawdown)
from portfolio.stats import sharpe_with_ci, win_rate_wilson
from portfolio.attribution import (alpha_by_hold_period, alpha_by_size,
                                   benchmark_sensitivity)
from portfolio.twr import build_twr_from_nav_summary
from visualizations.plots import (alpha_equity_curve, alpha_drawdown_chart,
                                  trade_alpha_waterfall, returns_scatter,
                                  monthly_alpha_heatmap, holdings_treemap)

_BENCHMARKS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "benchmarks.json")


def load_benchmarks():
    """Read the editable benchmark config. Re-read on every call so edits to
    benchmarks.json (or via the UI) take effect without a restart."""
    with open(_BENCHMARKS_PATH) as f:
        cfg = json.load(f)
    return cfg["map"], cfg.get("default", "QQQ"), cfg.get("yf_symbol", {})


def _fig_json(fig):
    """Plotly figure -> plain dict the browser's Plotly.js can render."""
    return json.loads(pio.to_json(fig))


def _nan_to_none(obj):
    """Recursively replace NaN floats with None so the payload is valid JSON."""
    if isinstance(obj, dict):
        return {k: _nan_to_none(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_nan_to_none(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


def build_dashboard_payload(currency="usd"):
    """Run the full pipeline and return everything the page needs, as a dict."""
    benchmark_map, default_bench, yf_symbol = load_benchmarks()

    # --- live fetch + parse + merge into the persistent ledger, then match ---
    raw_xml = fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)
    fresh = filter_stock_trades(parse_trades(raw_xml))
    trades = merge_trades(fresh)          # union into the ledger; compute from it
    closed, open_lots, orphans = match_round_trips(trades)

    # --- price data through TODAY (cached; today's bar refreshed by TTL) ---
    start = pd.concat([closed["entry_date"], open_lots["entry_date"]]).min()
    end = pd.Timestamp.today()
    all_tickers = pd.concat([closed["ticker"], open_lots["ticker"]]).unique()
    stock_prices = {tk: get_benchmark_prices(yf_symbol.get(tk, tk), start, end)
                    for tk in all_tickers}
    distinct = {b for bs in benchmark_map.values() for b in bs} | {default_bench}
    series_by_ticker = {bt: get_benchmark_prices(bt, start, end) for bt in distinct}
    usdsgd = get_benchmark_prices("USDSGD=X", start, end)
    fx_to_usd = {"EUR": get_benchmark_prices("EURUSD=X", start, end)}

    # --- compute alphas ---
    alphas = compute_all_trade_alphas(closed, benchmark_map, series_by_ticker,
                                      usdsgd, default_benchmark=default_bench)
    live = value_open_lots(open_lots, benchmark_map, series_by_ticker, usdsgd,
                           stock_prices, default_benchmark=default_bench)
    daily = build_daily_alpha(closed, open_lots, benchmark_map, stock_prices,
                              series_by_ticker, fx_to_usd, usdsgd, currency=currency,
                              default_benchmark=default_bench)

    col = f"alpha_{currency}"
    pnl_col = f"your_pnl_{currency}"      # your NET P&L (after commissions)
    primary_trades = alphas[alphas["is_primary"]]
    primary_open = live[live["is_primary"]]
    realized = primary_trades[col].sum()
    unrealized = primary_open[col].sum()
    # Your actual profit (not benchmark-relative): realized on closed trades +
    # unrealized on open positions, net of commissions, price-only.
    realized_pnl = primary_trades[pnl_col].sum()
    unrealized_pnl = primary_open[pnl_col].sum()

    # --- headline metrics ---
    metrics = {
        "currency": currency.upper(),
        # Your real profit
        "total_pnl": round(realized_pnl + unrealized_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        # Alpha (profit vs the benchmark counterfactual)
        "total_alpha": round(realized + unrealized, 2),
        "realized_alpha": round(realized, 2),
        "unrealized_alpha": round(unrealized, 2),
        "alpha_sharpe": round(alpha_sharpe(daily["alpha_ret"]), 2),
        "alpha_sortino": round(alpha_sortino(daily["alpha_ret"]), 2),
        "win_rate": round((primary_trades[col] > 0).mean() * 100, 1),
        "n_closed": int(len(primary_trades)),
        "n_open": int(len(primary_open)),
    }
    dd, peak, trough = alpha_max_drawdown(daily["cum_alpha_dollars"])
    metrics["max_drawdown"] = round(dd, 2)

    # --- the six figures, as JSON ---
    figures = {
        "equity_curve": _fig_json(alpha_equity_curve(daily, currency)),
        "drawdown": _fig_json(alpha_drawdown_chart(daily, currency)),
        "waterfall": _fig_json(trade_alpha_waterfall(alphas, currency)),
        "scatter": _fig_json(returns_scatter(alphas, currency)),
        "heatmap": _fig_json(monthly_alpha_heatmap(daily, currency)),
        "treemap": _fig_json(holdings_treemap(live, currency)),
    }

    # --- tables for the Trades / Positions tabs ---
    trade_cols = ["ticker", "benchmark", "entry_date", "exit_date", "hold_days",
                  "your_return", "benchmark_return", col]
    pos_cols = ["ticker", "benchmark", "quantity", "entry_price", "mark_price",
                f"value_{currency}", col]

    def records(df, cols):
        out = df[cols].copy()
        for c in out.columns:
            if pd.api.types.is_datetime64_any_dtype(out[c]):
                out[c] = out[c].dt.strftime("%Y-%m-%d")
        return out.round(4).to_dict(orient="records")

    # Surface unmatched sells as warnings rather than silently understating alpha.
    warnings = []
    if len(orphans):
        for _, o in orphans.iterrows():
            warnings.append(
                f"Unmatched sell: {o['unmatched_quantity']:g} {o['ticker']} on "
                f"{pd.Timestamp(o['datetime']).date()} has no opening trade in the "
                f"ledger - realized alpha may be understated. Backfill older trades "
                f"to fix (see backfill.py).")

    # --- Day 7 analytics ---
    # #10 statistical qualification of the headline metrics
    sh = sharpe_with_ci(daily["alpha_ret"])
    wins = int((primary_trades[col] > 0).sum())
    wr = win_rate_wilson(wins, len(primary_trades))
    stats = _nan_to_none({"sharpe": sh, "win_rate": wr})

    # #8 attribution (pure views over alphas already computed)
    def _buckets(df):
        d = df.copy()
        d["bucket"] = d["bucket"].astype(str)
        return d.round(4).to_dict(orient="records")

    attribution = {
        "by_hold_period": _buckets(alpha_by_hold_period(alphas, currency)),
        "by_size": _buckets(alpha_by_size(alphas, currency)),
    }
    # #9 benchmark sensitivity (uses the non-primary benchmark rows the engine emits)
    sens = benchmark_sensitivity(alphas, currency)
    sensitivity = sens.round(4).to_dict(orient="records") if not sens.empty else []

    # #6 account-level TWR - reads IBKR's own TWR from ChangeInNAV (if present)
    nav_summary = parse_change_in_nav(raw_xml)
    twr = None
    if nav_summary:
        qqq = series_by_ticker[default_bench]          # benchmark in base ccy (SGD)
        idx = qqq.index.union(usdsgd.index)
        bench_base = (qqq.reindex(idx).ffill() * usdsgd.reindex(idx).ffill()).dropna()
        twr = build_twr_from_nav_summary(nav_summary, bench_base)

    return {
        "metrics": metrics,
        "figures": figures,
        "trades": records(primary_trades, trade_cols),
        "positions": records(primary_open, pos_cols),
        "warnings": warnings,
        "stats": stats,
        "attribution": attribution,
        "sensitivity": sensitivity,
        "twr": twr,
        "as_of": end.strftime("%Y-%m-%d %H:%M"),
    }


if __name__ == "__main__":
    payload = build_dashboard_payload("usd")
    print("Payload keys:", list(payload.keys()))
    print("Metrics:", json.dumps(payload["metrics"], indent=2))
    print("Figure keys:", list(payload["figures"].keys()))
    print(f"{len(payload['trades'])} trades, {len(payload['positions'])} positions")
    print("As of:", payload["as_of"])
    print("\nSerializes to JSON:", "yes" if json.dumps(payload) else "no")
