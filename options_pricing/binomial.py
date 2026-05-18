import math
import numpy as np
from black_scholes import black_scholes

def binomial_tree(S, K, T, r, sigma, N, option_type='call'): 
    """
    S = current stock price
    K = strike price
    T = time to expiry in years
    r = risk-free interest rate (eg 0.05 for 0.5%)
    sigma = volatility (eg 0.20 for 20%)
    N = number of time steps in the tree
    """
    
    # split total time T into N small steps of length dt
    dt = T / N
    
    # movement of stock in one step, u = up factor, d = down factor
    u = np.exp(sigma * np.sqrt(dt))
    d = 1 / u # down mirrors up, so the tree recombines
    
    # the risk-neutral probability of an up move, not a real world prediction
    # probability that the expected return equals the risk-free rate
    p = (np.exp(r * dt) - d) / (u - d)
    
    # for discounting: how much $1 received one strep from now is worth today
    disc =  np.exp(-r * dt)
    
    # stock prices at expiry: after N steps, stock can be at N+1 different prices
    # if it went up i times and down (N-i) times: final price = S * u^i * d^(N-i)
    
    # number of up moves
    i = np.arange(N + 1)
    ST = S * (u ** i) * (d ** (N-i)) # ST is an array of all possible end prices sorted low to high
    
    # for a call: you profit if ST > K, otherwise worthless
    # for a put: you profit if ST < K, otherwise worthless
    
    if option_type == 'call':
        payoffs = np.maximum(ST-K, 0)
    else:
        payoffs = np.maximum(K-ST, 0)

    # start at expiry (step N) where we know the payoffs, then we step backwards to today (step 0)
    # at each step, every node's value is: disc * (p * value_if_up + (1-p) * value_if_down)
    # node's value = discounted average of where it could go next
    
    for step in range(N):
        # payoffs[1:] = values of the "up" children 
        # payoffs[:1] = values of the "down" children
        payoffs = disc * (p * payoffs[1:] + (1-p) * payoffs[:-1])
        # each iteration shrinks the array by 1: N+1 payoffs -> N values -> N-1 ... 1
    
    # After N iterations, we have a single number: today's price
    return payoffs[0]

if __name__ == "__main__":
    S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.20
    
    bs_call = black_scholes(S, K, T, r, sigma, 'call')
    bs_put = black_scholes(S, K, T, r, sigma, 'put')
    
    print("black scholes exact: ")
    print(f" call = {bs_call:.4f}")
    print(f" put = {bs_put:.4f}")
    print()
    
    print("binomial tree convergence: ")
    print(f" {'N':>6} {'Call':>10} {'Put':>10} {'Call err':>10} {'Put err':>10}")
    print(f" {'─'*6} {'─'*10} {'─'*10} {'─'*10} {'─'*10}")

    for N in [1, 5, 10, 25, 50, 100, 200, 500, 1000, 5000]:
        bt_call = binomial_tree(S, K, T, r, sigma, N, 'call')
        bt_put = binomial_tree(S, K, T, r, sigma, N, 'put')
        print(f" {N:>6} {bt_call:>10.4f} {bt_put:>10.4f}"
                f" {bt_call - bs_call:>+10.4f} {bt_put - bs_put:>+10.4f}")

        
    
