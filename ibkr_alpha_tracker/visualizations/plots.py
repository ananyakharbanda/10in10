import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import plotly.graph_objects as go

def alpha_drawdown_chart(daily_df, currency="usd"):
    """Underwater plot: how far below its high-water mark the cumulative
    alpha sits at each point. Reads the same daily DataFrame as the hero;
    the running peak is a view transform, not new alpha math."""
    cum = daily_df["cum_alpha_dollars"]
    dates = daily_df.index
    ccy = currency.upper()

    peak = cum.cummax()             # high-water mark to date
    underwater = cum - peak         # always <= 0
    trough_date = underwater.idxmin()
    max_dd = underwater.min()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=underwater, mode="lines", line=dict(color="#b91c1c", width=1.5),
        fill="tozeroy", fillcolor="rgba(239,68,68,0.30)", name="Below peak",
        hovertemplate="%{x|%Y-%m-%d}<br>Below peak: %{y:,.2f} " + ccy + "<extra></extra>"))
    fig.add_hline(y=0, line=dict(color="#9ca3af", width=1, dash="dash"))
    fig.add_annotation(
        x=trough_date, y=max_dd, text=f"Max drawdown {max_dd:,.0f} {ccy}",
        showarrow=True, arrowhead=2, ax=0, ay=-30, font=dict(color="#b91c1c"))

    fig.update_layout(
        title=f"Alpha Drawdown — depth below high-water mark ({ccy})",
        yaxis_title=f"Below peak ({ccy})", template="plotly_white", height=300,
        hovermode="x unified", margin=dict(l=70, r=20, t=50, b=40), showlegend=False)
    return fig

def alpha_equity_curve(daily_df, currency="usd"):
    """Hero chart: cumulative dollar alpha over time.

    A single line of cum_alpha_dollars (the gap between your book and the
    benchmark book), shaded green where you're ahead of the benchmark and
    red where you're behind. Reads only the daily curve DataFrame produced
    by portfolio.curve.build_daily_alpha - no new math here.
    """
    cum = daily_df["cum_alpha_dollars"]
    dates = daily_df.index
    ccy = currency.upper()

    pos = cum.clip(lower=0)   # positive part -> green fill; flat 0 where behind
    neg = cum.clip(upper=0)   # negative part -> red fill;   flat 0 where ahead

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=pos, mode="lines", line=dict(width=0),
        fill="tozeroy", fillcolor="rgba(34,197,94,0.30)",
        name="Ahead of benchmark", hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=dates, y=neg, mode="lines", line=dict(width=0),
        fill="tozeroy", fillcolor="rgba(239,68,68,0.30)",
        name="Behind benchmark", hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=dates, y=cum, mode="lines", line=dict(color="#111827", width=2),
        name=f"Cumulative alpha ({ccy})",
        hovertemplate="%{x|%Y-%m-%d}<br>Alpha: %{y:,.2f} " + ccy + "<extra></extra>"))
    fig.add_hline(y=0, line=dict(color="#9ca3af", width=1, dash="dash"))

    fig.update_layout(
        title=f"Cumulative Alpha vs Benchmark ({ccy})",
        yaxis_title=f"Cumulative alpha ({ccy})",
        template="plotly_white", height=420, hovermode="x unified",
        margin=dict(l=70, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    return fig


if __name__ == "__main__":
    import pandas as pd
    import config
    from data.ibkr_client import fetch_flex_report
    from data.parser import parse_trades, filter_stock_trades
    from data.benchmark import get_benchmark_prices
    from portfolio.matching import match_round_trips
    from portfolio.curve import build_daily_alpha

    trades = filter_stock_trades(parse_trades(
        fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)))
    closed, open_lots = match_round_trips(trades)

    BENCHMARK_MAP = {
        "NVDA": ["QQQ"], "MSFT": ["QQQ"], "GOOG": ["QQQ"], "AMZN": ["QQQ"],
        "QQQ": ["QQQ"], "TSM": ["QQQ", "SOXX"], "MC": ["FEZ"],
    }
    YF_SYMBOL = {"MC": "MC.PA"}

    start = pd.concat([closed["entry_date"], open_lots["entry_date"]]).min()
    end = pd.Timestamp.today()
    all_tickers = pd.concat([closed["ticker"], open_lots["ticker"]]).unique()
    stock_prices = {tk: get_benchmark_prices(YF_SYMBOL.get(tk, tk), start, end) for tk in all_tickers}
    distinct = {b for bs in BENCHMARK_MAP.values() for b in bs}
    series_by_ticker = {bt: get_benchmark_prices(bt, start, end) for bt in distinct}
    usdsgd = get_benchmark_prices("USDSGD=X", start, end)
    fx_to_usd = {"EUR": get_benchmark_prices("EURUSD=X", start, end)}

    for ccy in ("usd", "sgd"):
        daily = build_daily_alpha(closed, open_lots, BENCHMARK_MAP, stock_prices,
                                  series_by_ticker, fx_to_usd, usdsgd, currency=ccy)
        fig = alpha_equity_curve(daily, currency=ccy)
        out = f"hero_{ccy}.html"
        fig.write_html(out)
        print(f"Wrote {out} - open it in your browser")
