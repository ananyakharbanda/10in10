import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

from black_scholes import black_scholes
from greeks import greeks
from monte_carlo import monte_carlo
from binomial import binomial_tree

# app config
st.set_page_config(page_title="Black-Scholes Pricer", layout="wide")
st.title("Black-Scholes Option Pricer")

# sidebar sliders
st.sidebar.header("Parameters")
S     = st.sidebar.slider("Spot Price (S)",       50.0, 200.0, 100.0, 1.0)
K     = st.sidebar.slider("Strike Price (K)",     50.0, 200.0, 100.0, 1.0)
T     = st.sidebar.slider("Time to Expiry (yrs)", 0.05,   3.0,   1.0, 0.05)
r     = st.sidebar.slider("Risk-Free Rate (%)",   0.0,   15.0,   5.0, 0.5) / 100
sigma = st.sidebar.slider("Volatility (%)",        5.0,  80.0,  20.0, 1.0) / 100

# compute prices and greeks
call_price, call_d, call_g, call_v, call_t, call_r = greeks(S, K, T, r, sigma, 'call')
put_price,  put_d,  put_g,  put_v,  put_t,  put_r  = greeks(S, K, T, r, sigma, 'put')

# display prices
col1, col2 = st.columns(2)
with col1:
    st.subheader("Call")
    st.metric("Price", f"${call_price:.4f}")
with col2:
    st.subheader("Put")
    st.metric("Price", f"${put_price:.4f}")

# display greeks
st.subheader("Greeks")
gcols = st.columns(5)
labels = ["Delta", "Gamma", "Vega", "Theta", "Rho"]
call_vals = [call_d, call_g, call_v, call_t, call_r]
put_vals  = [put_d,  put_g,  put_v,  put_t,  put_r]

for i, col in enumerate(gcols):
    with col:
        st.markdown(f"**{labels[i]}**")
        st.write(f"Call: {call_vals[i]:+.4f}")
        st.write(f"Put:  {put_vals[i]:+.4f}")

# model comparison
st.subheader("Model Comparison")

bt_steps = st.sidebar.slider("Binomial Tree Steps", 10, 1000, 200, 10)
mc_sims  = st.sidebar.slider("Monte Carlo Simulations", 1000, 500000, 100000, 1000)

bt_call = binomial_tree(S, K, T, r, sigma, bt_steps, 'call')
bt_put  = binomial_tree(S, K, T, r, sigma, bt_steps, 'put')
mc_call, mc_call_se = monte_carlo(S, K, T, r, sigma, mc_sims, 'call')
mc_put,  mc_put_se  = monte_carlo(S, K, T, r, sigma, mc_sims, 'put')

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**Black-Scholes (exact)**")
    st.write(f"Call: ${call_price:.4f}")
    st.write(f"Put:  ${put_price:.4f}")
with col2:
    st.markdown(f"**Binomial Tree (N={bt_steps})**")
    st.write(f"Call: ${bt_call:.4f} (err: {bt_call - call_price:+.4f})")
    st.write(f"Put:  ${bt_put:.4f} (err: {bt_put - put_price:+.4f})")
with col3:
    st.markdown(f"**Monte Carlo (n={mc_sims:,})**")
    st.write(f"Call: ${mc_call:.4f} ± {mc_call_se:.4f} (err: {mc_call - call_price:+.4f})")
    st.write(f"Put:  ${mc_put:.4f} ± {mc_put_se:.4f} (err: {mc_put - put_price:+.4f})")

# convergence plot
st.subheader("Convergence")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

# binomial convergence
bt_ns = np.unique(np.geomspace(10, 2000, num=80).astype(int))
bt_errs = [abs(binomial_tree(S, K, T, r, sigma, int(n), 'call') - call_price) for n in bt_ns]

ax1.loglog(bt_ns, bt_errs, color='darkorange', linewidth=1)
ax1.axhline(0.01, color='gray', linestyle=':', linewidth=0.8, label='0.01 target')
ax1.set_xlabel('number of steps')
ax1.set_ylabel('absolute error')
ax1.set_title('Binomial Tree Convergence')
ax1.grid(True, alpha=0.3)
ax1.legend()

# monte carlo convergence
mc_ns = np.unique(np.geomspace(100, 200000, num=100).astype(int))
mc_prices = []
mc_ses = []
for n in mc_ns:
    p, se = monte_carlo(S, K, T, r, sigma, int(n), 'call')
    mc_prices.append(p)
    mc_ses.append(se)
mc_prices = np.array(mc_prices)
mc_ses = np.array(mc_ses)

ax2.semilogx(mc_ns, mc_prices, color='steelblue', linewidth=0.8)
ax2.fill_between(mc_ns,
                 mc_prices - 1.96 * mc_ses,
                 mc_prices + 1.96 * mc_ses,
                 alpha=0.25, color='steelblue', label='95% CI')
ax2.axhline(call_price, color='crimson', linestyle='--', linewidth=1.5,
            label=f'BS = {call_price:.4f}')
ax2.set_xlabel('number of simulations')
ax2.set_ylabel('call price estimate')
ax2.set_title('Monte Carlo Convergence')
ax2.grid(True, alpha=0.3)
ax2.legend()

plt.tight_layout()
st.pyplot(fig)

# payoff diagram
st.subheader("Payoff at Expiry")

spots = np.linspace(S * 0.5, S * 1.5, 300)
call_payoff = np.maximum(spots - K, 0) - call_price
put_payoff  = np.maximum(K - spots, 0) - put_price

fig2, ax = plt.subplots(figsize=(10, 5))
ax.plot(spots, call_payoff, color='steelblue', linewidth=2, label='Call P/L')
ax.plot(spots, put_payoff,  color='darkorange', linewidth=2, label='Put P/L')
ax.axhline(0, color='gray', linewidth=0.8)
ax.axvline(K, color='gray', linestyle=':', linewidth=0.8, label=f'Strike = {K}')
ax.axvline(S, color='green', linestyle='--', linewidth=0.8, label=f'Spot = {S}')

call_breakeven = K + call_price
put_breakeven  = K - put_price
ax.plot(call_breakeven, 0, 'o', color='steelblue', markersize=6)
ax.plot(put_breakeven,  0, 'o', color='darkorange', markersize=6)

ax.set_xlabel('Stock Price at Expiry')
ax.set_ylabel('Profit / Loss')
ax.legend()
ax.grid(True, alpha=0.3)
ax.set_title(f'S={S}, K={K}, T={T:.2f}yr, σ={sigma*100:.0f}%, r={r*100:.1f}%')
st.pyplot(fig2)

# greeks curves
st.subheader("Greeks vs Spot Price")

all_greeks_call = [greeks(s, K, T, r, sigma, 'call') for s in spots]
all_greeks_put  = [greeks(s, K, T, r, sigma, 'put')  for s in spots]

_, deltas_c, gammas_c, vegas_c, thetas_c, rhos_c = zip(*all_greeks_call)
_, deltas_p, gammas_p, vegas_p, thetas_p, rhos_p = zip(*all_greeks_put)

fig3, axes = plt.subplots(2, 3, figsize=(14, 8))

for ax, call_data, put_data, title in [
    (axes[0, 0], deltas_c,  deltas_p,  "Delta"),
    (axes[0, 1], gammas_c,  gammas_p,  "Gamma"),
    (axes[0, 2], vegas_c,   vegas_p,   "Vega"),
    (axes[1, 0], thetas_c,  thetas_p,  "Theta"),
    (axes[1, 1], rhos_c,    rhos_p,    "Rho"),
]:
    ax.plot(spots, call_data, label='call')
    ax.plot(spots, put_data,  label='put')
    ax.axvline(K, color='gray', linestyle=':', linewidth=0.8)
    ax.axvline(S, color='green', linestyle='--', linewidth=0.5)
    ax.set_title(title)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlabel('spot price')

axes[1, 2].axis('off')
plt.tight_layout()
st.pyplot(fig3)
