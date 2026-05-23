from collections import deque

import pandas as pd

EPS = 1e-9   # tolerance for floating-point share quantities


def _commission(ex):
    """IBKR ibCommission for an execution (negative = a cost paid). 0 if absent."""
    c = ex.get("commission", 0.0)
    return 0.0 if pd.isna(c) else float(c)


def match_round_trips(trades_df):
    """Match sells against the oldest open buys (FIFO), per ticker.

    Returns (closed_trips_df, open_lots_df):
      - closed_trips_df: one row per matched round-trip (entry + exit)
      - open_lots_df: buy lots never sold = your current open positions

    Commissions are per-execution, but FIFO splits executions into partial
    trips, so each execution's commission is apportioned across the trips it
    feeds, proportional to matched quantity. entry_commission / exit_commission
    are in native currency with IBKR's sign convention (negative = cost).
    """
    closed = []
    open_lots = []

    for ticker, group in trades_df.groupby("ticker"):
        group = group.sort_values("datetime")
        queue = deque()   # FIFO of open buy lots for this ticker

        for _, ex in group.iterrows():
            qty = ex["quantity"]
            if qty > 0:
                # A buy: push a new lot. Carry its commission PER SHARE so we can
                # apportion it as the lot gets consumed by one or more sells.
                queue.append({
                    "qty": qty,
                    "entry_date": ex["datetime"],
                    "entry_price": ex["price"],
                    "entry_fx": ex["fx_rate_to_base"],
                    "currency": ex["currency"],
                    "comm_per_share": _commission(ex) / qty,
                })
            else:
                # A sell: consume shares from the front of the queue (oldest first).
                sell_qty = -qty
                sell_comm_per_share = _commission(ex) / sell_qty   # apportion the sell too
                while sell_qty > EPS and queue:
                    lot = queue[0]
                    matched = min(sell_qty, lot["qty"])
                    closed.append({
                        "ticker": ticker,
                        "quantity": matched,
                        "entry_date": lot["entry_date"],
                        "entry_price": lot["entry_price"],
                        "entry_fx": lot["entry_fx"],
                        "exit_date": ex["datetime"],
                        "exit_price": ex["price"],
                        "exit_fx": ex["fx_rate_to_base"],
                        "currency": lot["currency"],
                        "entry_commission": matched * lot["comm_per_share"],
                        "exit_commission": matched * sell_comm_per_share,
                    })
                    lot["qty"] -= matched
                    sell_qty -= matched
                    if lot["qty"] <= EPS:
                        queue.popleft()
                # leftover sell_qty here = orphan sell (no opening lot in data);
                # dropped for now - Day 6 item #2 will surface these as a warning.

        # Anything left in the queue was never sold = still open.
        for lot in queue:
            if lot["qty"] > EPS:
                open_lots.append({
                    "ticker": ticker,
                    "quantity": lot["qty"],
                    "entry_date": lot["entry_date"],
                    "entry_price": lot["entry_price"],
                    "entry_fx": lot["entry_fx"],
                    "currency": lot["currency"],
                    "entry_commission": lot["qty"] * lot["comm_per_share"],
                })

    return pd.DataFrame(closed), pd.DataFrame(open_lots)


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config
    from data.ibkr_client import fetch_flex_report
    from data.parser import parse_trades, filter_stock_trades
    from data.ledger import merge_trades

    xml = fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)
    trades = merge_trades(filter_stock_trades(parse_trades(xml)))
    closed, open_lots = match_round_trips(trades)

    print(f"{len(closed)} closed round-trips:")
    print(closed[["ticker", "quantity", "entry_date", "exit_date", "entry_price",
                  "exit_price", "entry_commission", "exit_commission", "currency"]].to_string(index=False))
    print(f"\n{len(open_lots)} open lots:")
    print(open_lots[["ticker", "quantity", "entry_date", "entry_price",
                     "entry_commission", "currency"]].to_string(index=False))
