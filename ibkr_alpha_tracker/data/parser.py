import xml.etree.ElementTree as ET
import pandas as pd


def parse_one_trade(el):
    """Turn a single <Trade> XML element into a dict."""
    a = el.attrib
    return {
        # Stable per-execution ID from IBKR - the dedup key for the ledger.
        "trade_id": a.get("ibExecID"),
        "datetime": a.get("dateTime"),
        "ticker": a.get("underlyingSymbol") or a.get("symbol"),
        "action": a.get("buySell"),
        "quantity": float(a.get("quantity", 0)),
        "price": float(a.get("tradePrice", 0)),
        "proceeds": float(a.get("proceeds", 0)),
        "commission": float(a.get("ibCommission", 0)),
        "realized_pnl": float(a.get("fifoPnlRealized", 0)),
        "currency": a.get("currency"),
        "fx_rate_to_base": float(a.get("fxRateToBase", 0)),
        "open_close": a.get("openCloseIndicator"),
        "asset_class": a.get("assetCategory"),
    }


def parse_trades(xml_text):
    """Parse a full Flex report into a DataFrame of trades."""
    root = ET.fromstring(xml_text)
    trades = [parse_one_trade(el) for el in root.findall(".//Trade")]
    df = pd.DataFrame(trades)
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y%m%d;%H%M%S")
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


def filter_stock_trades(df):
    """Keep only real stock trades, dropping forex conversions and other
    asset classes."""
    return df[df["asset_class"] == "STK"].reset_index(drop=True)
