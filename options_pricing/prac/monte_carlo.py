import math
import numpy as np

def monte_carlo(S, K, T, r, sigma, n_sims, option_type='call', seed=42):
    rng = np.random.default_rng(seed)

    Z = rng.standard_normal(n_sims)

    ST = S * np.exp((r - 0.5 * sigma**2) * T + sigma * math.sqrt(T) * Z)

    if option_type == 'call':
        payoffs = np.maximum(ST - K, 0)
    else:
        payoffs = np.maximum(K - ST, 0)

    price = math.exp(-r * T) * np.mean(payoffs)
    se = math.exp(-r * T) * np.std(payoffs) / math.sqrt(n_sims)

    return price, se

if __name__ == "__main__":
    from black_scholes import black_scholes

    S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.20

    bs_call = black_scholes(S, K, T, r, sigma, 'call')
    mc_call, se = monte_carlo(S, K, T, r, sigma, 100_000)

    print(f"black-scholes: {bs_call:.4f}")
    print(f"monte carlo:   {mc_call:.4f} ± {se:.4f}")
