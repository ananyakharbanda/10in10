import numpy as np
import matplotlib.pyplot as plt
from black_scholes import black_scholes


def greeks(S, K, T, r, sigma, option_type='call'):
    h = 0.01

    # delta: how price changes with stock price
    delta = (black_scholes(S + h, K, T, r, sigma, option_type)
           - black_scholes(S - h, K, T, r, sigma, option_type)) / (2 * h)

    # gamma: how delta changes with stock price (second derivative)
    gamma = (black_scholes(S + h, K, T, r, sigma, option_type)
           - 2 * black_scholes(S, K, T, r, sigma, option_type)
           + black_scholes(S - h, K, T, r, sigma, option_type)) / (h ** 2)

    # vega: how price changes with volatility
    # divide by 100 so it's "per 1% move in vol"
    vega = (black_scholes(S, K, T, r, sigma + h, option_type)
          - black_scholes(S, K, T, r, sigma - h, option_type)) / (2 * h) / 100

    # theta: how price changes as time passes
    # divide by 365 so it's "per calendar day"
    theta = (black_scholes(S, K, T - h, r, sigma, option_type)
           - black_scholes(S, K, T + h, r, sigma, option_type)) / (2 * h) / 365

    # rho: how price changes with interest rate
    # divide by 100 so it's "per 1% move in rate"
    rho = (black_scholes(S, K, T, r + h, sigma, option_type)
         - black_scholes(S, K, T, r - h, sigma, option_type)) / (2 * h) / 100

    return delta, gamma, vega, theta, rho


if __name__ == "__main__":
    K, T, r, sigma = 100, 1.0, 0.05, 0.20

    # print greeks at ATM
    d, g, v, t, rh = greeks(100, K, T, r, sigma, 'call')
    print(f"ATM call greeks:  delta={d:.4f}  gamma={g:.4f}  vega={v:.4f}  theta={t:.6f}  rho={rh:.4f}")

    d, g, v, t, rh = greeks(100, K, T, r, sigma, 'put')
    print(f"ATM put greeks:   delta={d:.4f}  gamma={g:.4f}  vega={v:.4f}  theta={t:.6f}  rho={rh:.4f}")

    # ── Plot greeks vs spot price ──
    spots = np.linspace(60, 140, 300)

    call_greeks = [greeks(s, K, T, r, sigma, 'call') for s in spots]
    put_greeks  = [greeks(s, K, T, r, sigma, 'put')  for s in spots]

    # unpack into separate arrays
    call_delta, call_gamma, call_vega, call_theta, call_rho = zip(*call_greeks)
    put_delta,  put_gamma,  put_vega,  put_theta,  put_rho  = zip(*put_greeks)

    fig, axes = plt.subplots(3, 2, figsize=(12, 12))

    # delta
    axes[0, 0].plot(spots, call_delta, label='call')
    axes[0, 0].plot(spots, put_delta, label='put')
    axes[0, 0].set_title('Delta')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].axvline(K, color='gray', linestyle=':', linewidth=0.8)

    # gamma
    axes[0, 1].plot(spots, call_gamma, label='call')
    axes[0, 1].plot(spots, put_gamma, label='put', linestyle='--')
    axes[0, 1].set_title('Gamma')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].axvline(K, color='gray', linestyle=':', linewidth=0.8)

    # vega
    axes[1, 0].plot(spots, call_vega, label='call')
    axes[1, 0].plot(spots, put_vega, label='put', linestyle='--')
    axes[1, 0].set_title('Vega (per 1% vol)')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].axvline(K, color='gray', linestyle=':', linewidth=0.8)

    # theta
    axes[1, 1].plot(spots, call_theta, label='call')
    axes[1, 1].plot(spots, put_theta, label='put')
    axes[1, 1].set_title('Theta (per day)')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].axvline(K, color='gray', linestyle=':', linewidth=0.8)

    # rho
    axes[2, 0].plot(spots, call_rho, label='call')
    axes[2, 0].plot(spots, put_rho, label='put')
    axes[2, 0].set_title('Rho (per 1% rate)')
    axes[2, 0].legend()
    axes[2, 0].grid(True, alpha=0.3)
    axes[2, 0].axvline(K, color='gray', linestyle=':', linewidth=0.8)

    # hide the empty subplot
    axes[2, 1].axis('off')

    for ax in axes.flat:
        if ax.axison:
            ax.set_xlabel('spot price')

    fig.suptitle('Option Greeks vs Spot Price (K=100, T=1yr, σ=20%)', fontsize=14)
    plt.tight_layout()
    plt.savefig('greeks.png', dpi=150)
    print("\nsaved: greeks.png")
