from black_scholes import black_scholes
def greeks(S, K, T, r, sigma, option_type='call'):
    h = 0.01
    price = black_scholes(S, K, T, r, sigma, option_type)
    delta = (black_scholes(S + h, K, T, r, sigma, option_type)
           - black_scholes(S - h, K, T, r, sigma, option_type)) / (2 * h)
    gamma = (black_scholes(S + h, K, T, r, sigma, option_type)
           - 2 * price
           + black_scholes(S - h, K, T, r, sigma, option_type)) / (h ** 2)
    vega  = (black_scholes(S, K, T, r, sigma + h, option_type)
           - black_scholes(S, K, T, r, sigma - h, option_type)) / (2 * h) / 100
    theta = (black_scholes(S, K, T - h, r, sigma, option_type)
           - black_scholes(S, K, T + h, r, sigma, option_type)) / (2 * h) / 365
    rho   = (black_scholes(S, K, T, r + h, sigma, option_type)
           - black_scholes(S, K, T, r - h, sigma, option_type)) / (2 * h) / 100
    return price, delta, gamma, vega, theta, rho
