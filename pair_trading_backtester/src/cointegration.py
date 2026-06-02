import pandas as pd
import numpy as np
import statsmodels.api as sm
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import coint, adfuller

# to check for cointegration, load the csv and split the data into in-sample and out-of-sample

# 1) load the cleaned data from Day 1
prices = pd.read_csv("data/ko_pep.csv", index_col=0, parse_dates=True)

# 2) split: choose the pair & parameters on in-sample ONLY
in_sample  = prices.loc[:"2021-12-31"]      # 2015–2021, ~7 years
out_sample = prices.loc["2022-01-01":]      # 2022–2024, held back for Day 7

print("In-sample: ", in_sample.index.min().date(), "to", in_sample.index.max().date(), "| rows:", len(in_sample))
print("Out-sample:", out_sample.index.min().date(), "to", out_sample.index.max().date(), "| rows:", len(out_sample))

# 3) correlation on PRICE LEVELS (the misleading one, just shows that both went up over a decade, spurious correlation
corr_levels = in_sample["KO"].corr(in_sample["PEP"])

# 4) correlation on DAILY RETURNS (the honest one, checks for day-to-day percentage)
returns = in_sample.pct_change().dropna()
corr_returns = returns["KO"].corr(returns["PEP"])

print(f"\nCorrelation of price levels:  {corr_levels:.3f}")
print(f"Correlation of daily returns: {corr_returns:.3f}")

# 5) work in log prices to calculate the hedge ratio
log_prices = np.log(in_sample)
y = log_prices["KO"] # dependent variable
X = sm.add_constant(log_prices["PEP"]) # independent variable + intercept

model = sm.OLS(y, X).fit() # plot the straight line that fits log(KO) as a function of log(PEP)
beta = model.params["PEP"]

print(f"\nHedge ratio (beta): {beta:.3f}")
print(f"Intercept:          {model.params['const']:.3f}")

# 6) build the spread (after beta removes PEP's influence from KO, shows the gap)
spread = y - beta * log_prices["PEP"]
spread.plot(figsize=(12, 6), title="KO-PEP spread (in-sample), log scale")
plt.axhline(spread.mean(), color="red", linestyle="--", label="mean")
plt.ylabel("spread")
plt.legend()
plt.tight_layout()
# (no plt.show() here)

# 7) engle-granger cointegration test (the formal verdict)
score, pvalue, crit = coint(log_prices["KO"], log_prices["PEP"])
print(f"\nEngle-Granger cointegration test:")
print(f"  test statistic: {score:.3f}")
print(f"  p-value:        {pvalue:.4f}")

# 8) adf test directly on the spread (secondary read)
adf_stat, adf_p, *_ = adfuller(spread)
print(f"\nADF test on the spread:")
print(f"  test statistic: {adf_stat:.3f}")
print(f"  p-value:        {adf_p:.4f}")

plt.show()
