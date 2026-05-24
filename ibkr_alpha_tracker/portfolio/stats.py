"""Day 7 #10 - statistical qualification of the headline metrics.

Attaches confidence intervals so a metric reads "X (95% CI a..b)" instead of a
bare number, formalising the caveat that a small sample can't prove skill.
Uses normal-approx (z=1.96) so there's no scipy dependency."""
import numpy as np

Z95 = 1.959964


def sharpe_with_ci(period_returns, periods=252, z=Z95):
    """Annualised Sharpe of a return series, with a confidence interval.
    SE uses Lo (2002): SE(SR) = sqrt((1 + 0.5*SR^2)/n) on the per-period SR."""
    r = np.asarray(period_returns, dtype=float)
    r = r[~np.isnan(r)]
    n = len(r)
    if n < 3 or r.std(ddof=1) == 0:
        return {"sharpe": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": n}
    sr = r.mean() / r.std(ddof=1)                 # per-period Sharpe
    se = np.sqrt((1 + 0.5 * sr ** 2) / n)
    ann = np.sqrt(periods)
    return {"sharpe": round(sr * ann, 2),
            "lo": round((sr - z * se) * ann, 2),
            "hi": round((sr + z * se) * ann, 2), "n": n}


def win_rate_wilson(wins, n, z=Z95):
    """Win-rate (%) with a Wilson score interval - honest for small n."""
    if n == 0:
        return {"win_rate": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": 0}
    p = wins / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return {"win_rate": round(p * 100, 1),
            "lo": round(max(0, center - half) * 100, 1),
            "hi": round(min(1, center + half) * 100, 1), "n": n}


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    print("Sharpe CI (noisy daily series):",
          sharpe_with_ci(rng.normal(0.0003, 0.01, 360)))
    print("Win rate 3/4:", win_rate_wilson(3, 4))
    print("Win rate 30/40:", win_rate_wilson(30, 40))
    print("\nNote how the 4-trade CI is enormous vs the 40-trade one - that's the point.")
