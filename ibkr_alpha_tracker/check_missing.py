import config
from data.ibkr_client import fetch_flex_report
from data.parser import parse_trades, filter_stock_trades

fresh = filter_stock_trades(parse_trades(
    fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)))

print(f"{len(fresh)} stock trades")
print(f"trade_id blank on: {fresh['trade_id'].isna().sum()} rows\n")

# show the rows missing an ID
missing = fresh[fresh["trade_id"].isna()]
print(missing[["datetime", "ticker", "action", "quantity", "price"]].to_string(index=False))

import xml.etree.ElementTree as ET
xml = fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)
root = ET.fromstring(xml)
print("\nID coverage across ALL raw trade rows now:")
trades = root.findall(".//Trade")
for field in ["ibExecID", "transactionID", "tradeID"]:
    nonblank = sum(1 for t in trades if t.attrib.get(field))
    print(f"  {field:15} {nonblank}/{len(trades)}")
print("rows where ALL THREE blank:",
      sum(1 for t in trades if not (t.attrib.get("ibExecID") or
          t.attrib.get("transactionID") or t.attrib.get("tradeID"))))
