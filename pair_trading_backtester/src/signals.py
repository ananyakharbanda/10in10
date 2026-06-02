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

# generate raw position signal from z-score
entry_z = 2.0
exit_z  = 0.5

# +1 means long the spread (long KO, short PEP);
# -1 means short the spread (short KO, long PEP);
#  0 means flat (no position).
position = pd.Series(0, index=zscore.index)

# enter
position[zscore >  entry_z] = -1   # spread is high → short it (expect fall)
position[zscore < -entry_z] =  1   # spread is low  → long  it (expect rise)

# exit (when z comes back inside ±exit_z, close)
# will do this properly with a stateful loop next, placeholder for now

# shift forward one day: trade tomorrow on today's signal
position = position.shift(1).fillna(0)

print(f"\nPosition counts:")
print(position.value_counts())
