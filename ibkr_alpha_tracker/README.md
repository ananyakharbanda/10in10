# Alpha Tracker

A personal trading-analysis dashboard for Interactive Brokers accounts. It answers one
question: **am I actually a good trader, or should I just have bought the index?**

For every trade, it computes the dollar *alpha* — how much you made (or lost) versus the
counterfactual of putting the same capital into an appropriate benchmark (e.g. QQQ) on the
same dates. It also reports your **actual profit** (realized + unrealized, net of commissions),
risk-adjusted metrics, and six interactive charts — all in both USD and SGD, recomputed live
each time you open it.

> Personal project. Not investment advice. Reads your account read-only via IBKR Flex queries.

---

## What it does

- **Per-trade alpha** vs a per-instrument benchmark (the counterfactual: same capital into the index).
- **Your real P&L** — actual realized + unrealized profit, net of commissions.
- **Risk metrics** on the daily alpha series — Sharpe, Sortino, max drawdown.
- **Six charts** — cumulative alpha curve, drawdown, per-trade waterfall, return scatter,
  monthly heatmap, holdings treemap.
- **Dual currency** — every figure in USD and SGD, converted at each cashflow's own FX rate.
- **Always current** — recomputes from live IBKR + market data on each load.
- **Persistent trade ledger** — accumulates every trade ever seen, so history survives IBKR's
  365-day Flex window limit.
- **Editable benchmarks** — assign benchmarks to tickers from the UI, no code changes.

## How it works

```
IBKR Flex  ->  parse  ->  merge into local ledger  ->  FIFO match  ->  compute alpha
                                                                          |
                                          benchmark prices (yfinance) ----+
                                                                          v
                                              FastAPI  ->  JSON payload  ->  browser (Plotly.js)
```

The benchmark counterfactual uses a **matched-capital** model: each chunk of deployed capital
is independently compared against its benchmark over the actual holding period. Returns are
price-only on both sides (symmetric); alpha is net of your commissions.

## Project layout

```
ibkr_alpha_tracker/
├── app/
│   ├── dashboard.py      # orchestrator: runs the full pipeline -> one JSON payload
│   └── server.py         # FastAPI backend (+ optional Basic Auth gate)
├── data/
│   ├── ibkr_client.py    # Flex Web Service client (with date-range override)
│   ├── parser.py         # XML -> trades DataFrame (keeps ibExecID as trade_id)
│   ├── benchmark.py      # yfinance prices, cached with TTL + stale fallback
│   └── ledger.py         # persistent trade ledger (dedup by trade_id)
├── portfolio/
│   ├── matching.py       # FIFO round-trip matching (+ commission apportionment)
│   ├── counterfactual.py # per-trade alpha, dual-currency, net of commissions
│   ├── positions.py      # live unrealized alpha on open lots
│   └── curve.py          # daily alpha series + Sharpe / Sortino / drawdown
├── visualizations/
│   └── plots.py          # six Plotly figure builders
├── web/
│   └── index.html        # the dashboard (HTML + CSS + Plotly.js)
├── benchmarks.json       # editable ticker -> benchmark mapping
├── backfill.py           # one-off: pull a historical window into the ledger
├── config.py             # IBKR token + query IDs  (gitignored)
└── requirements.txt
```

## Setup

1. **Install dependencies** (Python 3.10+):
   ```bash
   pip install -r requirements.txt
   ```
2. **Create two IBKR Flex queries** (Activity statements) — one for Trades, one for Open
   Positions — selecting all fields. Note their query IDs and create a Flex Web Service token.
3. **Create `config.py`** at the project root:
   ```python
   import os
   IBKR_TOKEN        = os.environ.get("IBKR_TOKEN")        or "your-flex-token"
   TRADES_QUERY_ID   = os.environ.get("TRADES_QUERY_ID")   or "your-trades-query-id"
   POSITIONS_QUERY_ID= os.environ.get("POSITIONS_QUERY_ID")or "your-positions-query-id"
   ```
4. **(Optional) Backfill old trades.** IBKR Flex only returns the trailing 365 days. To
   capture older trades once into the ledger, set the window in `backfill.py` and run it:
   ```bash
   python backfill.py
   ```

## Run

```bash
uvicorn app.server:app --host 127.0.0.1 --port 8000
```

Open <http://localhost:8000>. The first load runs the full pipeline (a few seconds); the
payload is cached briefly so toggling currency is instant.

To require a password (recommended before exposing it anywhere), set:
```bash
export DASHBOARD_USER="you"
export DASHBOARD_PASSWORD="a-strong-password"
```

## Configuration

`benchmarks.json` maps each ticker to one or more benchmarks (the first is primary, used in
totals). Anything unlisted falls back to `default`. `yf_symbol` overrides the Yahoo symbol
where it differs (e.g. LVMH is `MC.PA`, not `MC`).

```json
{
  "default": "QQQ",
  "map": { "TSM": ["QQQ", "SOXX"], "MC": ["FEZ"] },
  "yf_symbol": { "MC": "MC.PA" }
}
```

## Methodology notes & limitations

- **Matched-capital model:** alpha comes only from deployed capital; deposits/withdrawals
  don't affect it (idle cash has no benchmark counterfactual).
- **Net of commissions; price-only** (dividends excluded symmetrically on both sides).
- **Benchmark treated as frictionless** — your commissions are charged to you, not the index.
- **FX:** each cashflow converts at its own date's rate; banked proceeds in the daily curve
  float at the daily rate (a documented, defensible SGD-only nuance).
- **Not yet implemented:** account-level time-weighted return (needs Cash Transactions),
  dividend crediting, and statistical significance on the metrics. With a small trade count,
  the risk metrics are correctly computed but not yet statistically meaningful.

## Tech

Python · pandas · FastAPI · yfinance · Plotly / Plotly.js. No database — a local CSV ledger
and a disk price cache.
