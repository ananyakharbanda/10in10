import pandas as pd

# to check for cointegration, load the csv and split the data into in-sample and out-of-sample

# 1) load the cleaned data from Day 1
prices = pd.read_csv("data/ko_pep.csv", index_col=0, parse_dates=True)

# 2) split: choose the pair & parameters on in-sample ONLY
in_sample  = prices.loc[:"2021-12-31"]      # 2015–2021, ~7 years
out_sample = prices.loc["2022-01-01":]      # 2022–2024, held back for Day 7

print("In-sample: ", in_sample.index.min().date(), "to", in_sample.index.max().date(), "| rows:", len(in_sample))
print("Out-sample:", out_sample.index.min().date(), "to", out_sample.index.max().date(), "| rows:", len(out_sample))

# 3) correlation on PRICE LEVELS (the misleading one) 
corr_levels = in_sample["KO"].corr(in_sample["PEP"])

# 4) correlation on DAILY RETURNS (the honest one)
returns = in_sample.pct_change().dropna()
corr_returns = returns["KO"].corr(returns["PEP"])

print(f"\nCorrelation of price levels:  {corr_levels:.3f}")
print(f"Correlation of daily returns: {corr_returns:.3f}")
