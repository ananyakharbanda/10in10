"""Day 7 #6 (part 1) - parse the Cash Transactions and daily NAV sections of a
Flex report. These power the account-level time-weighted return.

REQUIRES extra sections in your Flex query (see README / the note printed below):
  - Cash Transactions          -> deposits / withdrawals / dividends / fees
  - Equity Summary in Base     -> daily NAV (account value) in base currency
If those sections aren't in the report, the parsers return empty frames and the
dashboard simply omits the TWR card.
"""
import xml.etree.ElementTree as ET
import pandas as pd


def _to_date(s):
    """Flex dates come as YYYYMMDD or YYYYMMDD;HHMMSS."""
    if not s:
        return pd.NaT
    return pd.to_datetime(str(s).split(";")[0], format="%Y%m%d", errors="coerce")


def parse_cash_transactions(xml_text):
    """All cash transactions as a DataFrame (date, type, amount, currency,
    amount_base). amount_base converts to account base via fxRateToBase."""
    root = ET.fromstring(xml_text)
    rows = []
    for el in root.findall(".//CashTransaction"):
        a = el.attrib
        amount = float(a.get("amount", 0) or 0)
        fx = float(a.get("fxRateToBase", 1) or 1)
        rows.append({
            "date": _to_date(a.get("dateTime") or a.get("settleDate") or a.get("reportDate")),
            "type": a.get("type", ""),
            "amount": amount,
            "currency": a.get("currency"),
            "amount_base": amount * fx,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def external_flows_by_day(cash_df):
    """Net external flows (deposits +, withdrawals -) per day in BASE currency.
    Only Deposits/Withdrawals count as external for TWR - dividends, interest and
    fees are internal returns, not capital flows, so they're excluded here."""
    if cash_df.empty:
        return pd.Series(dtype=float)
    mask = cash_df["type"].str.contains("Deposit|Withdraw", case=False, na=False)
    ext = cash_df[mask]
    if ext.empty:
        return pd.Series(dtype=float)
    return ext.groupby("date")["amount_base"].sum()


def parse_change_in_nav(xml_text):
    """The ChangeInNAV summary row (one per statement period). IBKR computes its
    own time-weighted return here ('twr', already a percent), which is more
    authoritative than anything we could reconstruct, so we read it directly.
    Returns a dict, or None if the section isn't in the report."""
    root = ET.fromstring(xml_text)
    el = root.find(".//ChangeInNAV")
    if el is None:
        return None
    a = el.attrib

    def num(k):
        v = a.get(k)
        return float(v) if v not in (None, "") else None

    return {
        "from_date": _to_date(a.get("fromDate")),
        "to_date": _to_date(a.get("toDate")),
        "currency": a.get("currency"),
        "starting_value": num("startingValue"),
        "ending_value": num("endingValue"),
        "deposits_withdrawals": num("depositsWithdrawals"),
        "ibkr_twr_pct": num("twr"),          # IBKR's own TWR, in percent
    }


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config
    from data.ibkr_client import fetch_flex_report

    xml = fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)
    cash = parse_cash_transactions(xml)
    nav = parse_change_in_nav(xml)
    if cash.empty and nav is None:
        print("No Cash Transactions or ChangeInNAV in this report.")
        print("Add BOTH sections to your Flex query to enable account-level TWR:")
        print("  Flex Query -> Sections -> [x] Cash Transactions")
        print("                            [x] Change in NAV")
    else:
        print(f"{len(cash)} cash transactions; types: {sorted(cash['type'].unique()) if not cash.empty else '-'}")
        print("External flows by day (base):\n", external_flows_by_day(cash).to_string())
        if nav:
            print(f"\nChangeInNAV {nav['from_date'].date()} -> {nav['to_date'].date()} ({nav['currency']}):")
            print(f"  start {nav['starting_value']:.2f} -> end {nav['ending_value']:.2f}, "
                  f"deposits {nav['deposits_withdrawals']:.2f}")
            print(f"  IBKR time-weighted return: {nav['ibkr_twr_pct']:.2f}%")
        else:
            print("\nNo ChangeInNAV element.")
