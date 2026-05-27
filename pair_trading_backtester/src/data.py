import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

# --- Step 1: download adjusted prices ---
tickers = ["KO", "PEP"]
data = yf.download(tickers, start="2015-01-01", end="2024-12-31", auto_adjust=True)
prices = data["Close"]   # DataFrame with columns KO, PEP

# --- Step 2: inspect and clean ---
print("Missing values per ticker:")
print(prices.isna().sum())

print("\nSummary stats:")
print(prices.describe())

prices = prices.dropna()
print("\nShape after dropping missing rows:", prices.shape)
print("Date range:", prices.index.min().date(), "to", prices.index.max().date())

# --- Step 3: save a cached copy ---
prices.to_csv("data/ko_pep.csv")
print("\nSaved to data/ko_pep.csv")

# --- Step 4: look at it ---
prices.plot(figsize=(12, 6), title="KO vs PEP — Adjusted Close")
plt.ylabel("Price ($)")
plt.tight_layout()
plt.show()
