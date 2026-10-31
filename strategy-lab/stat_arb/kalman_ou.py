"""
Kalman y Ornstein-Uhlenbeck para pares
======================================
Implementación de los dos métodos de cantaro86/Financial-Models-Numerical-Methods
que se evalúan en backtest_walkforward.py:

- Notebook 5.1, "Kalman regression for the beta": hedge ratio dinámico.
      beta_k = beta_{k-1} + eta_k          eta ~ N(0, sigma_eta^2)   (paseo aleatorio)
      y_k    = alpha + beta_k x_k + eps_k  eps ~ N(0, sigma_eps^2)   (alpha fija)
  Calibración como en el notebook: sigma_eps = desviación típica del residuo
  MCO en la ventana de formación; sigma_eta por máxima verosimilitud (el autor
  avisa de que "la MLE a veces funciona, a veces no": si el óptimo cae en el
  límite inferior, la beta es en la práctica constante).

- Notebook 6.1, OU: ajuste por MCO de un AR(1) sobre el spread,
      s_{t+1} = a + b s_t + e,  kappa = -ln(b),  theta = a / (1 - b),
      sigma_eq = std(e) / sqrt(1 - b^2)   (desviación típica de equilibrio)
  y su regla de trading: abrir al cruzar theta +- 1 sigma_eq, cerrar a
  theta +- 0.1 sigma_eq (Cartea, Jaimungal y Penalva, 2015).

Todo trabaja sobre log-precios, igual que stat_arb_pairs.py.
"""

import numpy as np
from scipy.optimize import minimize_scalar


def ols_alpha_beta(y: np.ndarray, x: np.ndarray) -> tuple:
    """(alpha, beta, sigma_resid) de y = alpha + beta x por MCO."""
    X = np.column_stack([np.ones(len(x)), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    return coef[0], coef[1], resid.std(ddof=2)


def kalman_beta(y: np.ndarray, x: np.ndarray, alpha: float, beta0: float,
                sigma_eps: float, sigma_eta: float, p0: float = 1.0) -> dict:
    """
    Filtro de Kalman para beta_k con alpha fija (notebook 5.1, sección 3.1).

    Devuelve arrays de longitud n:
        beta_prior  beta_{k|k-1}: la que se conoce ANTES de ver y_k
        beta_post   beta_{k|k}:   tras incorporar y_k
        innov       r_k = y_k - alpha - beta_prior x_k
        S           varianza de la innovación
    Solo usa información hasta k en cada paso (filtro, no suavizador).
    """
    n = len(y)
    beta_prior, beta_post = np.empty(n), np.empty(n)
    innov, S = np.empty(n), np.empty(n)
    beta, P = beta0, p0
    q, r2 = sigma_eta ** 2, sigma_eps ** 2
    for k in range(n):
        P_pred = P + q
        beta_prior[k] = beta
        innov[k] = y[k] - alpha - beta * x[k]
        S[k] = x[k] ** 2 * P_pred + r2
        K = P_pred * x[k] / S[k]
        beta = beta + K * innov[k]
        P = (1 - K * x[k]) * P_pred
        beta_post[k] = beta
    return {'beta_prior': beta_prior, 'beta_post': beta_post, 'innov': innov, 'S': S}


def kalman_loglik(y, x, alpha, beta0, sigma_eps, sigma_eta) -> float:
    k = kalman_beta(y, x, alpha, beta0, sigma_eps, sigma_eta)
    return -0.5 * np.sum(np.log(2 * np.pi) + np.log(k['S']) + k['innov'] ** 2 / k['S'])


def calibrate_sigma_eta(y, x, alpha, beta0, sigma_eps,
                        bounds_log10: tuple = (-8.0, -1.0)) -> tuple:
    """
    sigma_eta por MLE en la ventana de formación (log10 acotado).
    Devuelve (sigma_eta, at_lower_bound).
    """
    res = minimize_scalar(lambda lg: -kalman_loglik(y, x, alpha, beta0, sigma_eps, 10 ** lg),
                          bounds=bounds_log10, method='bounded', options={'xatol': 0.05})
    lg = float(res.x)
    return 10 ** lg, lg <= bounds_log10[0] + 0.1


def calibrate_joint(y, x, alpha, beta0, bounds_log10: tuple = ((-5.0, -0.5), (-8.0, -1.0))) -> tuple:
    """
    (sigma_eps, sigma_eta) por MLE conjunta en la formación.

    Añadida tras el primer backtest: con sigma_eps = residuo MCO (receta del
    notebook 5.1) la innovación normalizada de un par tiene desviación típica
    ~0.4, no 1. En una regresión acción-índice el residuo MCO es ruido; en un
    par cointegrado es el propio spread, persistente y mucho más ancho que el
    ruido de medida. El diagnóstico sale de la formación, sin mirar retornos.
    """
    from scipy.optimize import minimize
    res = minimize(lambda p: -kalman_loglik(y, x, alpha, beta0, 10 ** p[0], 10 ** p[1]),
                   x0=[-2.0, -3.0], bounds=bounds_log10, method='L-BFGS-B')
    return 10 ** res.x[0], 10 ** res.x[1]


def fit_ou(spread: np.ndarray) -> dict:
    """
    OU por MCO sobre AR(1) (notebook 6.1). None si no hay reversión
    (b fuera de (0, 1)).
    """
    s0, s1 = spread[:-1], spread[1:]
    X = np.column_stack([np.ones(len(s0)), s0])
    (a, b), *_ = np.linalg.lstsq(X, s1, rcond=None)
    if not 0 < b < 1:
        return None
    resid = s1 - X @ np.array([a, b])
    kappa = -np.log(b)
    return {'kappa': kappa, 'theta': a / (1 - b), 'half_life': np.log(2) / kappa,
            'sigma_eq': resid.std(ddof=2) / np.sqrt(1 - b ** 2)}
