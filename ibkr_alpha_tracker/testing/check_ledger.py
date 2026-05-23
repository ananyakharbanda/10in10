import pandas as pd
from data.ledger import load_ledger, LEDGER_PATH

print("Ledger path:", LEDGER_PATH)
import os
print("Exists:", os.path.exists(LEDGER_PATH))

led = load_ledger()
print(f"\n{len(led)} trades in ledger")
print("Tickers:", sorted(led["ticker"].unique()))
print("MC present:", "MC" in led["ticker"].values)
if "MC" in led["ticker"].values:
    print(led[led["ticker"]=="MC"][["datetime","ticker","quantity","price"]].to_string(index=False))
