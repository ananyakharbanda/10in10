# black scholes pricing for a European call
    
import math

def norm_cdf(x):
    # standard normal CDF using the error function
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def black_scholes(S, K, T, r, sigma, option_type='call'):
    """
    S = spot price
    K = strike price
    T = time to expiry (years)
    r = risk-free rate (annual & continuous)
    sigma = volatility (annual)
    """
    d1 = (math.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    if option_type == 'call':
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:
        return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)

if __name__ == "__main__":
    S, K, T, r, sigma = 100, 100, 1, 0.05, 0.20
    C = black_scholes(S, K, T, r, sigma, 'call')
    P = black_scholes(S, K, T, r, sigma, 'put')

    # Must hold: C - P == S - K * e^(-rT)
    assert abs((C - P) - (S - K * math.exp(-r * T))) < 1e-10
