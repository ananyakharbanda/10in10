import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

from black_scholes import black_scholes
from greeks import greeks

# streamlit app
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

# payoff diagram
st.subheader("Payoff at Expiry")

spots = np.linspace(S * 0.5, S * 1.5, 300)
call_payoff = np.maximum(spots - K, 0) - call_price
put_payoff  = np.maximum(K - spots, 0) - put_price

fig, ax = plt.subplots(figsize=(10, 5))
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
st.pyplot(fig)

# greeks curves
st.subheader("Greeks vs Spot Price")

all_greeks_call = [greeks(s, K, T, r, sigma, 'call') for s in spots]
all_greeks_put  = [greeks(s, K, T, r, sigma, 'put')  for s in spots]

_, deltas_c, gammas_c, vegas_c, thetas_c, rhos_c = zip(*all_greeks_call)
_, deltas_p, gammas_p, vegas_p, thetas_p, rhos_p = zip(*all_greeks_put)

fig2, axes = plt.subplots(2, 3, figsize=(14, 8))

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
st.pyplot(fig2)
