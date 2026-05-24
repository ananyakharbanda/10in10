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


def parse_daily_nav(xml_text):
    """Daily account NAV (base currency) from the Equity Summary section, as a
    date-indexed Series. Empty if the section isn't in the report."""
    root = ET.fromstring(xml_text)
    rows = []
    for el in root.findall(".//EquitySummaryByReportDateInBase"):
        a = el.attrib
        d = _to_date(a.get("reportDate"))
        total = a.get("total")
        if d is not pd.NaT and total is not None:
            rows.append((d, float(total)))
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series(dict(rows)).sort_index()
    s.index = pd.to_datetime(s.index)
    return s


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config
    from data.ibkr_client import fetch_flex_report

    xml = fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)
    cash = parse_cash_transactions(xml)
    nav = parse_daily_nav(xml)
    if cash.empty and nav.empty:
        print("No Cash Transactions or Equity Summary in this report.")
        print("Add BOTH sections to your Flex query to enable account-level TWR:")
        print("  Flex Query -> Sections -> [x] Cash Transactions")
        print("                            [x] Equity Summary in Base (Change in NAV)")
    else:
        print(f"{len(cash)} cash transactions; types: {sorted(cash['type'].unique()) if not cash.empty else '-'}")
        print("External flows by day (base):\n", external_flows_by_day(cash).to_string())
        print(f"\nDaily NAV points: {len(nav)}  range {nav.index.min()} .. {nav.index.max()}" if not nav.empty else "No NAV series.")
