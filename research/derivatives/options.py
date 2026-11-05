"""Small option-pricing library: Black-Scholes with Greeks, implied volatility, a Cox-Ross-Rubinstein binomial tree
(European and American) and a Monte Carlo pricer with antithetic and control variates.

All functions take: S spot, K strike, T years to expiry, r continuously compounded rate, q dividend yield,
sigma volatility, kind "call" or "put". test_options.py checks them against each other.
"""
import math

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


def _d1_d2(S, K, T, r, q, sigma):
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return d1, d1 - sigma * math.sqrt(T)


def bs_price(S, K, T, r, sigma, kind="call", q=0.0):
    if T <= 0:
        return max(S - K, 0.0) if kind == "call" else max(K - S, 0.0)
    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    if kind == "call":
        return S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)


def bs_greeks(S, K, T, r, sigma, kind="call", q=0.0):
    """Delta, gamma, vega (per 1.00 of vol), theta (per year) and rho (per 1.00 of rate)."""
    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    disc_q, disc_r, pdf = math.exp(-q * T), math.exp(-r * T), norm.pdf(d1)
    gamma = disc_q * pdf / (S * sigma * math.sqrt(T))
    vega = S * disc_q * pdf * math.sqrt(T)
    if kind == "call":
        delta = disc_q * norm.cdf(d1)
        theta = (-S * disc_q * pdf * sigma / (2 * math.sqrt(T)) - r * K * disc_r * norm.cdf(d2)
                 + q * S * disc_q * norm.cdf(d1))
        rho = K * T * disc_r * norm.cdf(d2)
    else:
        delta = -disc_q * norm.cdf(-d1)
        theta = (-S * disc_q * pdf * sigma / (2 * math.sqrt(T)) + r * K * disc_r * norm.cdf(-d2)
                 - q * S * disc_q * norm.cdf(-d1))
        rho = -K * T * disc_r * norm.cdf(-d2)
    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho}


def implied_vol(price, S, K, T, r, kind="call", q=0.0, lo=1e-4, hi=5.0):
    """Volatility that makes the Black-Scholes price equal `price` (Brent's method). NaN if no solution."""
    intrinsic = max(S * math.exp(-q * T) - K * math.exp(-r * T), 0) if kind == "call" else \
        max(K * math.exp(-r * T) - S * math.exp(-q * T), 0)
    if price <= intrinsic + 1e-10:
        return float("nan")
    f = lambda s: bs_price(S, K, T, r, s, kind, q) - price
    try:
        return brentq(f, lo, hi, xtol=1e-8)
    except ValueError:
        return float("nan")


def binomial_price(S, K, T, r, sigma, kind="call", q=0.0, steps=500, american=False):
    """Cox-Ross-Rubinstein tree. With american=True the holder may exercise at every node."""
    dt = T / steps
    u = math.exp(sigma * math.sqrt(dt))
    d = 1 / u
    p = (math.exp((r - q) * dt) - d) / (u - d)
    disc = math.exp(-r * dt)
    j = np.arange(steps + 1)
    prices = S * u ** (steps - j) * d ** j
    values = np.maximum(prices - K, 0) if kind == "call" else np.maximum(K - prices, 0)
    for i in range(steps - 1, -1, -1):
        values = disc * (p * values[:-1] + (1 - p) * values[1:])
        if american:
            prices = S * u ** (i - np.arange(i + 1)) * d ** np.arange(i + 1)
            exercise = prices - K if kind == "call" else K - prices
            values = np.maximum(values, exercise)
    return float(values[0])


def mc_price(S, K, T, r, sigma, kind="call", q=0.0, paths=200_000, seed=0, control_variate=True):
    """Monte Carlo under geometric Brownian motion, with antithetic draws and (optionally) the discounted
    terminal stock price as a control variate, whose expectation is known exactly. Returns (price, std error)."""
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(paths // 2)
    z = np.concatenate([z, -z])
    ST = S * np.exp((r - q - 0.5 * sigma ** 2) * T + sigma * math.sqrt(T) * z)
    payoff = np.maximum(ST - K, 0) if kind == "call" else np.maximum(K - ST, 0)
    half = paths // 2
    # antithetic draws come in dependent pairs, so everything is done on pair averages
    x = 0.5 * (payoff[:half] + payoff[half:]) * math.exp(-r * T)
    if control_variate:
        y = 0.5 * (ST[:half] + ST[half:]) * math.exp(-r * T)
        ey = S * math.exp(-q * T)
        # the coefficient must be estimated on the pair averages too: on raw paths the antithetic pairing
        # already removes the linear part, and a raw-path beta adds variance instead of removing it
        beta = np.cov(x, y)[0, 1] / y.var(ddof=1)
        x = x - beta * (y - ey)
    return float(x.mean()), float(x.std(ddof=1) / math.sqrt(len(x)))
