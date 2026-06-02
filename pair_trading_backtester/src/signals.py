import pandas as pd
import numpy as np
import statsmodels.api as sm
import matplotlib.pyplot as plt

# reload and reconstruct with what cointegration.py left us
prices = pd.read_csv("data/ko_pep.csv", index_col=0, parse_dates=True)
in_sample = prices.loc[:"2021-12-31"]
log_prices = np.log(in_sample)

y = log_prices["KO"]
X = sm.add_constant(log_prices["PEP"])
beta = sm.OLS(y, X).fit().params["PEP"]

spread = y - beta * log_prices["PEP"]

# z-score using FULL-SAMPLE mean and std (THIS IS WRONG)
# z_full = (spread - spread.mean()) / spread.std()

# print(f"Full-sample z-score: mean={z_full.mean():.3f}, std={z_full.std():.3f}")
# print(f"Range: {z_full.min():.2f} to {z_full.max():.2f}")

# z-score using ROLLING-WINDOW mean and std (the right way)
window = 30   # trading days, ~6 weeks

rolling_mean = spread.rolling(window).mean()
rolling_std  = spread.rolling(window).std()

zscore = (spread - rolling_mean) / rolling_std

print(f"\nRolling z-score: mean={zscore.mean():.3f}, std={zscore.std():.3f}")
print(f"NaNs at start (window warm-up): {zscore.isna().sum()}")
