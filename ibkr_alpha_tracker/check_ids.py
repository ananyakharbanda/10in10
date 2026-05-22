import config
from data.ibkr_client import fetch_flex_report
import xml.etree.ElementTree as ET

xml = fetch_flex_report(config.IBKR_TOKEN, config.TRADES_QUERY_ID)
root = ET.fromstring(xml)
trades = root.findall(".//Trade")

print(f"{len(trades)} trade elements\n")
for field in ["ibExecID", "transactionID", "tradeID"]:
    vals = [t.attrib.get(field, "") for t in trades]
    nonblank = [v for v in vals if v]
    unique = len(set(nonblank))
    print(f"{field:15} present on {len(nonblank)}/{len(trades)},  {unique} unique values")
