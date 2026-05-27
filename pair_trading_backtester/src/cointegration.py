import pandas as pd

# to check for cointegration, load the csv and split the data into in-sample and out-of-sample

# 1) load the cleaned data from Day 1
prices = pd.read_csv("data/ko_pep.csv", index_col=0, parse_dates=True)

# 2) split: choose the pair & parameters on in-sample ONLY
in_sample  = prices.loc[:"2021-12-31"]      # 2015–2021, ~7 years
out_sample = prices.loc["2022-01-01":]      # 2022–2024, held back for Day 7

print("In-sample: ", in_sample.index.min().date(), "to", in_sample.index.max().date(), "| rows:", len(in_sample))
print("Out-sample:", out_sample.index.min().date(), "to", out_sample.index.max().date(), "| rows:", len(out_sample))
