# parses a single trade element

import xml.etree.ElementTree as ET
import pandas as pd


def parse_one_trade(el):
    """Turn a single <Trade> XML element into a dict."""
    a = el.attrib   # all the XML attributes as a dictionary
    return {
        "datetime": a.get("dateTime"), # get returns None if a key is missing
        "ticker": a.get("underlyingSymbol") or a.get("symbol"),
        "action": a.get("buySell"),
        "quantity": float(a.get("quantity", 0)), # if quantity is missing, use 0 because you cannot float(None)
        "price": float(a.get("tradePrice", 0)),
        "proceeds": float(a.get("proceeds", 0)),
        "commission": float(a.get("ibCommission", 0)),
        "realized_pnl": float(a.get("fifoPnlRealized", 0)),
        "currency": a.get("currency"),
        "fx_rate_to_base": float(a.get("fxRateToBase", 0)),
        "open_close": a.get("openCloseIndicator"),
        "asset_class": a.get("assetCategory"),
    }

# looping over each trade to build the dataframe

def parse_trades(xml_text):
    """Parse a full Flex report into a DataFrame of trades."""
    root = ET.fromstring(xml_text)

    trades = [parse_one_trade(el) for el in root.findall(".//Trade")] # searches at any depth below the root with list comprehension

    df = pd.DataFrame(trades) # pandas to turn dictionary into a table
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y%m%d;%H%M%S") # converts into real pandas timestamps
    df = df.sort_values("datetime").reset_index(drop=True) # sorts all values chronologically
    return df
