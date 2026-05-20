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
