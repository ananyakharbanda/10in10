import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.graph_objects as go


def alpha_equity_curve(daily_df, currency="usd"):
    """Hero chart: cumulative dollar alpha over time, shaded green where you're
    ahead of the benchmark and red where behind. Reads only the daily curve
    DataFrame from portfolio.curve.build_daily_alpha - no new math."""
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
        title=dict(text=f"Cumulative Alpha vs Benchmark ({ccy})", y=0.95),
        yaxis_title=f"Cumulative alpha ({ccy})",
        template="plotly_white", height=420, hovermode="x unified",
        margin=dict(l=70, r=20, t=70, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, x=0))
    return fig


def alpha_drawdown_chart(daily_df, currency="usd"):
    """Underwater plot: how far below its high-water mark the cumulative alpha
    sits each day. Reads the same daily DataFrame as the hero; the running
    peak is a view transform, not new alpha math. Always <= 0 by construction."""
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
        title=f"Alpha Drawdown - depth below high-water mark ({ccy})",
        yaxis_title=f"Below peak ({ccy})", template="plotly_white", height=300,
        hovermode="x unified", margin=dict(l=70, r=20, t=50, b=40), showlegend=False)
    return fig


def trade_alpha_waterfall(alphas_df, currency="usd"):
    """One bar per closed trade, sorted by exit date (ticker as tiebreaker),
    green/red by sign, cumulating to the total alpha. Reads closed-trade
    alphas (primary benchmark only, so multi-benchmark trades aren't
    double-counted)."""
    df = alphas_df[alphas_df["is_primary"]].copy().sort_values(["exit_date", "ticker"])
    col = f"alpha_{currency}"
    ccy = currency.upper()
    labels = [f"{r.ticker}<br>{pd.Timestamp(r.exit_date).date()}" for r in df.itertuples()]

    fig = go.Figure(go.Waterfall(
        orientation="v", measure=["relative"] * len(df),
        x=labels, y=df[col],
        text=[f"{v:+,.0f}" for v in df[col]], textposition="outside",
        connector=dict(line=dict(color="#9ca3af")),
        increasing=dict(marker=dict(color="#22c55e")),
        decreasing=dict(marker=dict(color="#ef4444"))))
    total = df[col].sum()
    fig.add_hline(y=0, line=dict(color="#9ca3af", width=1))
    fig.update_layout(
        title=f"Per-Trade Alpha Contribution ({ccy}) - total {total:+,.0f}",
        yaxis_title=f"Alpha ({ccy})", template="plotly_white", height=420,
        margin=dict(l=70, r=20, t=50, b=60), showlegend=False)
    return fig


def returns_scatter(alphas_df, currency="usd"):
    """Each trade's own return (y) vs its benchmark's return (x) over the same
    hold. The 45-degree dashed line is break-even: above it you beat the index.
    Reads your_return + benchmark_return - no math here. Axes are padded around
    the actual data (not a fixed window) and kept square so the diagonal stays
    a true 45 degrees."""
    df = alphas_df[alphas_df["is_primary"]].copy()
    yr = df["your_return"] * 100
    br = df["benchmark_return"] * 100

    allvals = pd.concat([yr, br])
    lo, hi = allvals.min(), allvals.max()
    pad = max((hi - lo) * 0.25, 3)
    lo, hi = lo - pad, hi + pad
    lo, hi = min(lo, 0), max(hi, 0)   # keep the break-even origin in view
    colors = ["#22c55e" if b else "#ef4444" for b in (yr >= br)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[lo, hi], y=[lo, hi], mode="lines",
        line=dict(color="#9ca3af", dash="dash"), name="Break-even (45deg)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=br, y=yr, mode="markers+text",
        marker=dict(size=13, color=colors, line=dict(width=1, color="#374151")),
        text=df["ticker"], textposition="top center",
        hovertemplate="%{text}<br>You: %{y:.1f}%<br>Benchmark: %{x:.1f}%<extra></extra>"))
    fig.update_layout(
        title=f"Your Return vs Benchmark Return, per trade ({currency.upper()})",
        xaxis_title="Benchmark return (%)", yaxis_title="Your return (%)",
        template="plotly_white", height=460, showlegend=False,
        xaxis=dict(range=[lo, hi], zeroline=True),
        yaxis=dict(range=[lo, hi], zeroline=True, scaleanchor="x", scaleratio=1),
        margin=dict(l=70, r=20, t=50, b=50))
    return fig


if __name__ == "__main__":
    import config
    from data.ibkr_client import fetch_flex_report
    from data.parser import parse_trades, filter_stock_trades
    from data.benchmark import get_benchmark_prices
    from portfolio.matching import match_round_trips
    from portfolio.counterfactual import compute_all_trade_alphas
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

    alphas = compute_all_trade_alphas(closed, BENCHMARK_MAP, series_by_ticker, usdsgd)

    for ccy in ("usd", "sgd"):
        daily = build_daily_alpha(closed, open_lots, BENCHMARK_MAP, stock_prices,
                                  series_by_ticker, fx_to_usd, usdsgd, currency=ccy)
        alpha_equity_curve(daily, ccy).write_html(f"hero_{ccy}.html")
        alpha_drawdown_chart(daily, ccy).write_html(f"drawdown_{ccy}.html")
        trade_alpha_waterfall(alphas, ccy).write_html(f"waterfall_{ccy}.html")
        returns_scatter(alphas, ccy).write_html(f"scatter_{ccy}.html")
        print(f"Wrote hero_{ccy}, drawdown_{ccy}, waterfall_{ccy}, scatter_{ccy} (.html)")
