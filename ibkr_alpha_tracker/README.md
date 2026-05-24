# Alpha Tracker

A personal trading-analysis dashboard for Interactive Brokers accounts. It answers one
question from several honest angles: **am I actually a good trader, or should I just have
bought the index?**

For every trade it computes the dollar *alpha* — how much you made (or lost) versus the
counterfactual of putting the same capital into an appropriate benchmark (e.g. QQQ) on the
same dates. It also reports your **actual profit**, an **account-level time-weighted return**
(the whole-account view, cash drag included), attribution, benchmark-sensitivity, and
confidence intervals — all in both USD and SGD, recomputed live each time you open it.

> Personal project. Not investment advice. Reads your account read-only via IBKR Flex queries.

---

## What it does

- **Per-trade alpha** vs a per-instrument benchmark (the counterfactual: same capital into the index).
- **Your real P&L** — actual realized + unrealized profit, net of commissions.
- **Account-level TWR** — time-weighted return for the whole account (reads IBKR's own figure
  from Change in NAV), compared to the index over the same window. Reveals cash drag that
  per-trade alpha can't see.
- **Risk metrics** on the daily alpha series — Sharpe, Sortino, max drawdown.
- **Statistical qualification** — 95% confidence intervals on Sharpe (Lo 2002) and win rate
  (Wilson score), so small-sample numbers are read honestly.
- **Attribution** — alpha broken down by holding period and by position size.
- **Benchmark sensitivity** — how alpha shifts under alternative benchmark choices.
- **Six charts** — cumulative alpha curve, drawdown, per-trade waterfall, return scatter,
  monthly heatmap, holdings treemap.
- **Dual currency** — every figure in USD and SGD, converted at each cashflow's own FX rate.
- **Always current** — recomputes from live IBKR + market data on each load (optional
  background precompute for instant page loads).
- **Persistent trade ledger** — accumulates every trade ever seen, so history survives IBKR's
  365-day Flex window limit.
- **Editable benchmarks** — assign benchmarks to tickers from the UI, no code changes.
- **Loud failures** — unmatched ("orphan") sells surface as a warning banner instead of
  silently understating performance.

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
price-only on both sides (symmetric); alpha is net of your commissions. Account-level TWR is a
separate, complementary view that includes idle cash.

## Project layout

```
ibkr_alpha_tracker/
├── app/
│   ├── __init__.py
│   ├── dashboard.py      # orchestrator: runs the full pipeline -> one JSON payload
│   └── server.py         # FastAPI backend (+ optional auth gate + background precompute)
├── data/
│   ├── ibkr_client.py    # Flex Web Service client (with date-range override)
│   ├── parser.py         # XML -> trades DataFrame (keeps ibExecID as trade_id)
│   ├── benchmark.py      # yfinance prices, cached with TTL + stale fallback
│   ├── ledger.py         # persistent trade ledger (dedup by trade_id, last-seen-wins)
│   └── cash.py           # Cash Transactions + Change-in-NAV parsers (for TWR)
├── portfolio/
│   ├── matching.py       # FIFO round-trip matching (+ commission apportionment, orphans)
│   ├── counterfactual.py # per-trade alpha, dual-currency, net of commissions
│   ├── positions.py      # live unrealized alpha on open lots
│   ├── curve.py          # daily alpha series + Sharpe / Sortino / drawdown
│   ├── metrics.py        # trade-level summary stats (win rate, profit factor, etc.)
│   ├── stats.py          # Sharpe & win-rate confidence intervals
│   ├── attribution.py    # alpha by holding period / size; benchmark sensitivity
│   └── twr.py            # account-level time-weighted return
├── visualizations/
│   └── plots.py          # six Plotly figure builders
├── web/
│   └── index.html        # the dashboard (HTML + CSS + Plotly.js)
├── testing/
│   ├── verify.py         # end-to-end reconciliation check (run after any change)
│   ├── check_ids.py      # one-off: confirm trade-id fields are present/unique
│   ├── check_ledger.py   # one-off: inspect the ledger contents
│   └── check_missing.py  # one-off: find trades missing a trade_id
├── backfill.py           # one-off: pull a historical window into the ledger
├── benchmarks.json       # editable ticker -> benchmark mapping
├── config.py             # IBKR token + query IDs  (gitignored)
├── requirements.txt
└── README.md
```

## Setup

1. **Install dependencies** (Python 3.10+):
   ```bash
   pip install -r requirements.txt
   ```
2. **Create IBKR Flex queries** (Activity statements) and a Flex Web Service token. In the
   Trades query, enable these sections:
   - **Trades** (required)
   - **Cash Transactions** — for deposits/withdrawals (enables account TWR)
   - **Change in NAV** — for the account's time-weighted return
   Create a separate **Open Positions** query as well. Note the query IDs.
3. **Create `config.py`** at the project root:
   ```python
   import os
   IBKR_TOKEN         = os.environ.get("IBKR_TOKEN")         or "your-flex-token"
   TRADES_QUERY_ID    = os.environ.get("TRADES_QUERY_ID")    or "your-trades-query-id"
   POSITIONS_QUERY_ID = os.environ.get("POSITIONS_QUERY_ID") or "your-positions-query-id"
   ```
4. **(Optional) Backfill old trades.** IBKR Flex only returns the trailing 365 days. To capture
   older trades once into the ledger, set the window in `backfill.py` and run it:
   ```bash
   python backfill.py
   ```

## Run

```bash
uvicorn app.server:app --host 127.0.0.1 --port 8000
```

Open <http://localhost:8000>. The first load runs the full pipeline (a few seconds); the
payload is cached briefly so toggling currency is instant.

Optional: refresh both currencies in the background so loads are always instant, and require a
password before exposing the app anywhere:
```bash
export PRECOMPUTE_SECONDS=300        # 0 disables (default)
export DASHBOARD_USER="you"
export DASHBOARD_PASSWORD="a-strong-password"
```

## Verify

After any change, re-check that every number reconciles. Run the verifier **as a module from
the project root** (so imports resolve):

```bash
python -m testing.verify
```

It recomputes the pipeline independently and asserts the key invariants — alpha decomposition,
the three-engine reconciliation (curve endpoint == realized + unrealized), real-P&L identities,
and that the dashboard's metrics match the recompute. The other `testing/check_*.py` scripts are
one-off diagnostics; run them the same way, e.g. `python -m testing.check_ledger`. To inspect the
cash/NAV parsing for TWR, run `python -m data.cash`.

## Configuration

`benchmarks.json` maps each ticker to one or more benchmarks (the first is primary, used in
totals). Anything unlisted falls back to `default`. `yf_symbol` overrides the Yahoo symbol where
it differs (e.g. LVMH is `MC.PA`, not `MC`).

```json
{
  "default": "QQQ",
  "map": { "TSM": ["QQQ", "SOXX"], "MC": ["FEZ"] },
  "yf_symbol": { "MC": "MC.PA" }
}
```

## Methodology notes & limitations

- **Two complementary views.** *Per-trade alpha* uses a matched-capital model — it judges your
  decisions only while capital was deployed, so idle cash doesn't affect it. *Account TWR*
  judges the whole account every day, so it does include cash drag. They can disagree, and the
  gap is informative (e.g. good picks but costly time spent in cash).
- **Net of commissions; price-only** (dividends excluded symmetrically on both sides). The
  benchmark is treated as frictionless — your commissions are charged to you, not the index.
- **TWR** is read directly from IBKR's `ChangeInNAV` (their official figure) and compared to the
  benchmark's buy-and-hold return over the same window, in account base currency.
- **FX:** each cashflow converts at its own date's rate; banked proceeds in the daily alpha
  curve float at the daily rate (a documented, defensible SGD-only nuance).
- **Ledger:** last-seen-wins, so broker corrections to in-window trades are picked up;
  cancellations that change a trade's id are not auto-removed (known limitation).
- **Small sample.** Confidence intervals are shown precisely because the trade count is small —
  the metrics are correctly computed but not yet statistically conclusive about skill.
- **Future:** crediting dividends on both sides (now easy, since Cash Transactions are already
  fetched) would upgrade returns from price-only to total-return.

## Tech

Python · pandas · NumPy · FastAPI · yfinance · Plotly / Plotly.js. No database — a local CSV
ledger and a disk price cache.
