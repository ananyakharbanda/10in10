"""One-off backfill: fetch a historical 365-day window (one that still contains
trades aged out of the rolling window) and merge it into the ledger. The ledger
dedupes by trade_id, so overlapping with the normal window is harmless - only
the genuinely-missing trades (e.g. the MC buy) get added.

Edit FROM_DATE / TO_DATE and re-run for each historical window you need; the
ledger stitches them together into one complete history. Each window must span
<= 365 days (IBKR's hard limit)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from data.ibkr_client import fetch_flex_report
from data.parser import parse_trades, filter_stock_trades
from data.ledger import merge_trades

FROM_DATE = "20250101"   # yyyymmdd - must be <= 365 days before TO_DATE
TO_DATE = "20251231"

if __name__ == "__main__":
    print(f"Backfilling window {FROM_DATE} -> {TO_DATE} ...")
    xml = fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID,
                            from_date=FROM_DATE, to_date=TO_DATE)
    fresh = filter_stock_trades(parse_trades(xml))
    print(f"Window returned {len(fresh)} stock trades:")
    print(fresh[["datetime", "ticker", "action", "quantity", "price"]].to_string(index=False))

    ledger = merge_trades(fresh)
    print(f"\nLedger now holds {len(ledger)} trades across "
          f"{ledger['ticker'].nunique()} tickers.")
    print("MC (LVMH) present:", "MC" in ledger["ticker"].values)
    mc = ledger[ledger["ticker"] == "MC"]
    if len(mc):
        print(mc[["datetime", "action", "quantity", "price"]].to_string(index=False))
