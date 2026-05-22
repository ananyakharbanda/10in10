"""Persistent trade ledger: an append-only local record of every trade ever
seen, so trades that age out of IBKR's rolling Flex window are never lost.

Each fetch is merged into the ledger by trade_id (IBKR's ibExecID), so
re-fetched trades are deduped and only genuinely new ones are added. Everything
downstream computes from the ledger, not the raw fetch."""
import os
import pandas as pd

LEDGER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trade_ledger.csv")


def load_ledger(path=LEDGER_PATH):
    """Load the stored ledger, or an empty frame if it doesn't exist yet."""
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["datetime"])


def merge_trades(fresh_df, path=LEDGER_PATH):
    """Union fresh trades into the ledger by trade_id, persist, and return the
    full accumulated trade set.

    First-seen wins: a trade_id already in the ledger is kept as-is; only
    genuinely new trade_ids are appended. (Corrections/cancellations by IBKR
    are not re-applied - a deliberate simplification; rare for retail.)"""
    if "trade_id" not in fresh_df.columns or fresh_df["trade_id"].isna().any():
        raise ValueError(
            "Trades are missing trade_id - the parser must populate ibExecID "
            "before merging, or dedup can't work safely.")

    ledger = load_ledger(path)
    if ledger.empty:
        combined = fresh_df.copy()
    else:
        new_rows = fresh_df[~fresh_df["trade_id"].isin(ledger["trade_id"])]
        combined = pd.concat([ledger, new_rows], ignore_index=True)

    combined = combined.sort_values("datetime").reset_index(drop=True)
    combined.to_csv(path, index=False)
    return combined


if __name__ == "__main__":
    # Functional check: dedup must keep real trades and drop re-fetched copies.
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "_ledger_test.csv")
    if os.path.exists(tmp):
        os.remove(tmp)

    day1 = pd.DataFrame({
        "trade_id": ["A", "B", "C"], "ticker": ["AMZN", "NVDA", "QQQ"],
        "datetime": pd.to_datetime(["2026-03-03", "2026-03-03", "2026-03-27"]),
        "quantity": [4.0, 1.0, 6.0]})
    # Day 2 re-fetches A,B,C (overlap) and adds a NEW trade D.
    day2 = pd.DataFrame({
        "trade_id": ["A", "B", "C", "D"], "ticker": ["AMZN", "NVDA", "QQQ", "MSFT"],
        "datetime": pd.to_datetime(["2026-03-03","2026-03-03","2026-03-27","2026-05-22"]),
        "quantity": [4.0, 1.0, 6.0, 3.0]})

    l1 = merge_trades(day1, tmp)
    l2 = merge_trades(day2, tmp)
    print(f"After day 1: {len(l1)} trades  (expect 3)")
    print(f"After day 2: {len(l2)} trades  (expect 4, NOT 7 - duplicates skipped)")
    assert len(l1) == 3 and len(l2) == 4, "DEDUP FAILED"
    print("Tickers in ledger:", sorted(l2["ticker"].tolist()))
    print("Dedup works: re-fetched trades skipped, new trade D added.")
    os.remove(tmp)
