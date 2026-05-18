import numpy as np
import matplotlib.pyplot as plt

from black_scholes import black_scholes
from monte_carlo import monte_carlo
from binomial import binomial_tree

S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.20

bs_call = black_scholes(S, K, T, r, sigma, 'call')
bs_put  = black_scholes(S, K, T, r, sigma, 'put')

print(f"black-scholes:  call = {bs_call:.4f}  put = {bs_put:.4f}\n")

# ── Convergence table ──
print(f"  {'n':>8}  {'MC call':>10}  {'±':>6}  {'BT call':>10}  {'MC err':>10}  {'BT err':>10}")
print(f"  {'─'*8}  {'─'*10}  {'─'*6}  {'─'*10}  {'─'*10}  {'─'*10}")

for n in [100, 500, 1_000, 5_000, 10_000, 50_000, 100_000, 500_000]:
    mc_call, se = monte_carlo(S, K, T, r, sigma, n, 'call')

    if n <= 10_000:
        bt_call = binomial_tree(S, K, T, r, sigma, n, 'call')
        bt_str  = f"{bt_call:>10.4f}"
        bt_err  = f"{bt_call - bs_call:>+10.4f}"
    else:
        bt_str  = "       --"
        bt_err  = "       --"

    print(f"  {n:>8,}  {mc_call:>10.4f}  {se:>6.4f}  {bt_str}  {mc_call - bs_call:>+10.4f}  {bt_err}")

# ── Convergence plot ──
mc_ns   = np.unique(np.geomspace(100, 500_000, num=150).astype(int))
bt_ns   = np.unique(np.geomspace(10, 5_000, num=80).astype(int))

mc_errs = []
for n in mc_ns:
    price, _ = monte_carlo(S, K, T, r, sigma, int(n), 'call')
    mc_errs.append(abs(price - bs_call))

bt_errs = []
for n in bt_ns:
    price = binomial_tree(S, K, T, r, sigma, int(n), 'call')
    bt_errs.append(abs(price - bs_call))

plt.figure(figsize=(10, 6))
plt.loglog(mc_ns, mc_errs, color='steelblue', linewidth=0.8, label='Monte Carlo')
plt.loglog(bt_ns, bt_errs, color='darkorange', linewidth=0.8, label='Binomial Tree')
plt.axhline(0.01, color='gray', linestyle=':', linewidth=0.8, label='0.01 target')
plt.xlabel('n (simulations / tree steps)')
plt.ylabel('absolute error vs Black-Scholes')
plt.title('Convergence: Monte Carlo vs Binomial Tree')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('convergence.png', dpi=150)
print("\nsaved: convergence.png")
