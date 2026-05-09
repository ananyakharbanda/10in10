import math
import numpy as np

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
    p = (np.exp(r * dt) - d) / (u -d)
    
    # for discounting: how much $1 received one strep from now is worth today
    disc =  np.exp(-r * dt)
    
    
    
