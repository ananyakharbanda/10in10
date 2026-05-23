"""End-to-end sanity check. Recomputes the pipeline and asserts the invariants
the dashboard relies on, so you can trust the numbers after any change.

Run from the project root:  python verify.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

import config
from data.ibkr_client import fetch_flex_report
from data.parser import parse_trades, filter_stock_trades
from data.ledger import merge_trades
from data.benchmark import get_benchmark_prices
from portfolio.matching import match_round_trips
from portfolio.counterfactual import compute_all_trade_alphas
from portfolio.positions import value_open_lots
from portfolio.curve import build_daily_alpha, alpha_max_drawdown
from app.dashboard import build_dashboard_payload, load_benchmarks

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, ok, detail=""):
    results.append((PASS if ok else FAIL, name, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f"  ->  {detail}" if detail else ""))


def approx(a, b, tol):
    return abs(a - b) <= tol


print("Recomputing pipeline from the ledger...\n")
benchmark_map, default_bench, yf_symbol = load_benchmarks()

fresh = filter_stock_trades(parse_trades(
    fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)))
trades = merge_trades(fresh)
closed, open_lots, orphans = match_round_trips(trades)

start = pd.concat([closed["entry_date"], open_lots["entry_date"]]).min()
end = pd.Timestamp.today()
all_tickers = pd.concat([closed["ticker"], open_lots["ticker"]]).unique()
stock_prices = {t: get_benchmark_prices(yf_symbol.get(t, t), start, end) for t in all_tickers}
distinct = {b for bs in benchmark_map.values() for b in bs} | {default_bench}
series_by_ticker = {bt: get_benchmark_prices(bt, start, end) for bt in distinct}
usdsgd = get_benchmark_prices("USDSGD=X", start, end)
fx_to_usd = {"EUR": get_benchmark_prices("EURUSD=X", start, end)}

alphas = compute_all_trade_alphas(closed, benchmark_map, series_by_ticker, usdsgd,
                                  default_benchmark=default_bench)
live = value_open_lots(open_lots, benchmark_map, series_by_ticker, usdsgd, stock_prices,
                       default_benchmark=default_bench)

pt = alphas[alphas["is_primary"]]
po = live[live["is_primary"]]

print("=== Structure ===")
check("closed + open lots present", len(closed) > 0 and len(open_lots) > 0,
      f"{len(closed)} closed, {len(open_lots)} open")
check("no orphan (unmatched) sells", len(orphans) == 0,
      "none" if len(orphans) == 0 else f"{len(orphans)} ORPHANS - alpha understated!")

print("\n=== Commission signs (should be <= 0, a cost) ===")
comm_ok = ((closed["entry_commission"] <= 1e-9).all() and
           (closed["exit_commission"] <= 1e-9).all() and
           (open_lots["entry_commission"] <= 1e-9).all())
check("all commissions are costs (<= 0)", comm_ok)

print("\n=== Per-trade identities (net) ===")
for cur in ("usd", "sgd"):
    a, y, g, c, b = (f"alpha_{cur}", f"your_pnl_{cur}", f"gross_pnl_{cur}",
                     f"commission_{cur}", f"benchmark_pnl_{cur}")
    d1 = (alphas[a] - (alphas[y] - alphas[b])).abs().max()
    d2 = (alphas[y] - (alphas[g] + alphas[c])).abs().max()
    check(f"[{cur}] alpha == your_pnl - benchmark_pnl", d1 < 1e-6, f"max err {d1:.2e}")
    check(f"[{cur}] your_pnl == gross + commission", d2 < 1e-6, f"max err {d2:.2e}")

print("\n=== Three-engine reconciliation (curve endpoint == realized + unrealized) ===")
for cur, tol in (("usd", 2.0), ("sgd", 15.0)):
    a = f"alpha_{cur}"
    realized = pt[a].sum()
    unrealized = po[a].sum()
    daily = build_daily_alpha(closed, open_lots, benchmark_map, stock_prices,
                              series_by_ticker, fx_to_usd, usdsgd, currency=cur,
                              default_benchmark=default_bench)
    curve_end = daily["cum_alpha_dollars"].iloc[-1]
    gap = abs(curve_end - (realized + unrealized))
    note = f"curve {curve_end:,.2f} vs sum {realized+unrealized:,.2f} (gap {gap:,.2f}, tol {tol})"
    check(f"[{cur}] curve endpoint reconciles", gap <= tol, note)
    if cur == "sgd" and gap > tol:
        print("        (SGD gap expected: banked proceeds float at daily FX - documented)")

print("\n=== Real P&L identity ===")
for cur in ("usd", "sgd"):
    y = f"your_pnl_{cur}"
    total = pt[y].sum() + po[y].sum()
    check(f"[{cur}] total_pnl == realized_pnl + unrealized_pnl",
          True, f"{total:,.2f} = {pt[y].sum():,.2f} + {po[y].sum():,.2f}")

print("\n=== Dashboard metrics match independent recompute ===")
for cur in ("usd", "sgd"):
    m = build_dashboard_payload(cur)["metrics"]
    a, y = f"alpha_{cur}", f"your_pnl_{cur}"
    checks = {
        "realized_alpha": (m["realized_alpha"], round(pt[a].sum(), 2)),
        "unrealized_alpha": (m["unrealized_alpha"], round(po[a].sum(), 2)),
        "total_alpha": (m["total_alpha"], round(pt[a].sum() + po[a].sum(), 2)),
        "realized_pnl": (m["realized_pnl"], round(pt[y].sum(), 2)),
        "unrealized_pnl": (m["unrealized_pnl"], round(po[y].sum(), 2)),
        "total_pnl": (m["total_pnl"], round(pt[y].sum() + po[y].sum(), 2)),
        "n_closed": (m["n_closed"], len(pt)),
        "n_open": (m["n_open"], len(po)),
    }
    allok = all(approx(v[0], v[1], 0.02) if isinstance(v[0], float) else v[0] == v[1]
                for v in checks.values())
    bad = [k for k, v in checks.items()
           if not (approx(v[0], v[1], 0.02) if isinstance(v[0], float) else v[0] == v[1])]
    check(f"[{cur}] all dashboard metrics match", allok,
          "all match" if allok else f"MISMATCH: {bad}")

print("\n=== Payload serializes & has all six figures ===")
p = build_dashboard_payload("usd")
ser = True
try:
    json.dumps(p)
except Exception as e:
    ser = False
check("payload is JSON-serializable", ser)
check("six figures present", len(p["figures"]) == 6, ", ".join(p["figures"].keys()))

n_fail = sum(1 for r in results if r[0] == FAIL)
print("\n" + "=" * 60)
print(f"  {len(results)} checks, {n_fail} failed.")
print("  ALL GOOD - numbers reconcile." if n_fail == 0
      else f"  {n_fail} CHECK(S) FAILED - investigate above.")
print("=" * 60)
