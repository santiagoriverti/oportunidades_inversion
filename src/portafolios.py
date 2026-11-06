"""Optimizadores de portafolio, todos sin ventas en corto (pesos >= 0, suman 1) y con peso máximo por activo.

Detalle matemático en docs/METODOLOGIA.md §6. Se usa scipy (SLSQP / L-BFGS-B): sin dependencias pesadas.

    pesos_iguales          1/N (referencia ingenua, difícil de vencer)
    minima_varianza        mínimo w'Σw
    maximo_sharpe          máximo (w'μ - rf) / σ  (Markowitz, portafolio tangente; formulación convexa)
    volatilidad_objetivo   máximo w'μ con σ <= objetivo
    paridad_riesgo         cada activo aporta el mismo riesgo (Spinu 2013, problema convexo)
    hrp                    Hierarchical Risk Parity (López de Prado 2016)
    frontera_eficiente     mínima varianza para cada retorno objetivo
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.optimize import minimize
from scipy.spatial.distance import squareform

NOMBRES = {
    "pesos_iguales": "Pesos iguales (1/N)",
    "minima_varianza": "Mínima varianza",
    "maximo_sharpe": "Máximo Sharpe (Markowitz)",
    "volatilidad_objetivo": "Volatilidad objetivo",
    "paridad_riesgo": "Paridad de riesgo",
    "hrp": "HRP (López de Prado)",
    "black_litterman": "Black-Litterman con señales",
    "oportunidades": "Oportunidades (paridad de riesgo)",
}
# Los optimizados concentran: se les eliminan las posiciones chicas. Los diversificados conservan todas.
CONCENTRADOS = ("minima_varianza", "maximo_sharpe", "volatilidad_objetivo", "black_litterman")


def _tope(n: int, peso_maximo: float) -> float:
    """Peso máximo factible: si n * peso_maximo < 1 la única opción es 1/n."""
    return max(float(peso_maximo), 1.0 / n)


def _suma_uno(n):
    return {"type": "eq", "fun": lambda w: np.sum(w) - 1.0, "jac": lambda w: np.ones(n)}


def limpiar_pesos(w: pd.Series, minimo: float = 0.0, maximo: float = 1.0) -> pd.Series:
    """Saca posiciones menores a ``minimo`` (de a una, la más chica primero), renormaliza y aplica el tope
    ``maximo`` redistribuyendo el excedente entre las demás en proporción a su peso."""
    w = pd.Series(w, dtype=float).clip(lower=0.0).fillna(0.0)
    if w.sum() <= 0:
        raise ValueError("Pesos vacíos")
    w = w / w.sum()
    if minimo > 0:
        while (w > 0).sum() > 1:
            chicos = w[(w > 0) & (w < minimo)]
            if chicos.empty:
                break
            w[chicos.idxmin()] = 0.0
            w = w / w.sum()
    tope = max(maximo, 1.0 / max((w > 0).sum(), 1))
    for _ in range(200):
        exceso = (w - tope).clip(lower=0.0).sum()
        if exceso < 1e-12:
            break
        w = w.clip(upper=tope)
        libres = (w > 0) & (w < tope - 1e-12)
        if not libres.any():
            break
        w[libres] += exceso * w[libres] / w[libres].sum()
    return w / w.sum()


def pesos_iguales(activos: list[str]) -> pd.Series:
    return pd.Series(1.0 / len(activos), index=list(activos))


def maximo_retorno_factible(mu: pd.Series, peso_maximo: float) -> pd.Series:
    """El portafolio de máximo retorno con el tope: llena con el tope los de mayor retorno."""
    tope = _tope(len(mu), peso_maximo)
    w = pd.Series(0.0, index=mu.index)
    resto = 1.0
    for s in mu.sort_values(ascending=False).index:
        w[s] = min(tope, resto)
        resto -= w[s]
        if resto <= 1e-12:
            break
    return w


def minima_varianza(cov: pd.DataFrame, peso_maximo: float = 1.0) -> pd.Series:
    S = cov.to_numpy()
    n = len(S)
    x0 = np.full(n, 1.0 / n)
    res = minimize(lambda w: w @ S @ w, x0, jac=lambda w: 2.0 * S @ w, method="SLSQP",
                   bounds=[(0.0, _tope(n, peso_maximo))] * n, constraints=[_suma_uno(n)],
                   options={"maxiter": 1000, "ftol": 1e-14})
    w = np.clip(res.x if res.success else x0, 0.0, None)
    return pd.Series(w / w.sum(), index=cov.index)


def maximo_sharpe(mu: pd.Series, cov: pd.DataFrame, rf: float, peso_maximo: float = 1.0
                  ) -> tuple[pd.Series, str]:
    """Portafolio tangente. Formulación convexa (Cornuejols y Tütüncü): con y = w / κ,
    minimizar y'Σy sujeto a (μ - rf)'y = 1, Σy = κ, 0 <= y_i <= tope·κ. Devuelve (pesos, nota)."""
    mu = mu.reindex(cov.index)
    S = cov.to_numpy()
    n = len(S)
    ex = (mu - rf).to_numpy()
    tope = _tope(n, peso_maximo)
    w_max = maximo_retorno_factible(mu - rf, peso_maximo).to_numpy()
    if not np.isfinite(ex).all():
        raise ValueError("Hay retornos esperados no finitos")
    if ex @ w_max <= 0:
        return minima_varianza(cov, peso_maximo), ("ningún portafolio factible rinde más que la tasa libre de "
                                                   "riesgo: se usa mínima varianza")
    k0 = 1.0 / (ex @ w_max)
    z0 = np.concatenate([w_max * k0, [k0]])
    cons = [
        {"type": "eq", "fun": lambda z: ex @ z[:n] - 1.0, "jac": lambda z: np.concatenate([ex, [0.0]])},
        {"type": "eq", "fun": lambda z: np.sum(z[:n]) - z[n], "jac": lambda z: np.concatenate([np.ones(n), [-1.0]])},
        {"type": "ineq", "fun": lambda z: tope * z[n] - z[:n],
         "jac": lambda z: np.hstack([-np.eye(n), np.full((n, 1), tope)])},
    ]
    res = minimize(lambda z: z[:n] @ S @ z[:n], z0, jac=lambda z: np.concatenate([2.0 * S @ z[:n], [0.0]]),
                   method="SLSQP", bounds=[(0.0, None)] * n + [(1e-12, None)], constraints=cons,
                   options={"maxiter": 3000, "ftol": 1e-15})
    if res.success and res.x[n] > 0:
        w = np.clip(res.x[:n] / res.x[n], 0.0, None)
        return pd.Series(w / w.sum(), index=cov.index), ""
    # Respaldo: maximizar el Sharpe directamente desde el portafolio de máximo retorno
    res2 = minimize(lambda w: -(ex @ w) / np.sqrt(w @ S @ w), w_max, method="SLSQP",
                    bounds=[(0.0, tope)] * n, constraints=[_suma_uno(n)], options={"maxiter": 3000})
    if res2.success:
        w = np.clip(res2.x, 0.0, None)
        return pd.Series(w / w.sum(), index=cov.index), "resuelto con el método de respaldo"
    return minima_varianza(cov, peso_maximo), "el optimizador no convergió: se usa mínima varianza"


def volatilidad_objetivo(mu: pd.Series, cov: pd.DataFrame, objetivo: float, peso_maximo: float = 1.0
                         ) -> tuple[pd.Series, str]:
    """Máximo retorno esperado con volatilidad anual <= objetivo. Devuelve (pesos, nota)."""
    mu = mu.reindex(cov.index)
    S, m = cov.to_numpy(), mu.to_numpy()
    n = len(S)
    w_mv = minima_varianza(cov, peso_maximo)
    vol_mv = float(np.sqrt(w_mv @ S @ w_mv))
    if objetivo <= vol_mv + 1e-9:
        return w_mv, (f"la volatilidad objetivo ({objetivo:.1%}) es menor que la mínima posible "
                      f"({vol_mv:.1%}): se usa mínima varianza")
    w_mx = maximo_retorno_factible(mu, peso_maximo)
    if float(np.sqrt(w_mx @ S @ w_mx)) <= objetivo:
        return w_mx, "el portafolio de máximo retorno ya tiene una volatilidad menor al objetivo"
    res = minimize(lambda w: -(m @ w), w_mv.to_numpy(), jac=lambda w: -m, method="SLSQP",
                   bounds=[(0.0, _tope(n, peso_maximo))] * n,
                   constraints=[_suma_uno(n), {"type": "ineq", "fun": lambda w: objetivo ** 2 - w @ S @ w,
                                               "jac": lambda w: -2.0 * S @ w}],
                   options={"maxiter": 2000, "ftol": 1e-14})
    if not res.success:
        return w_mv, "el optimizador no convergió: se usa mínima varianza"
    w = np.clip(res.x, 0.0, None)
    return pd.Series(w / w.sum(), index=cov.index), ""


def paridad_riesgo(cov: pd.DataFrame) -> pd.Series:
    """Igual contribución al riesgo: minimizar ½ y'Σy - Σ b_i ln y_i (b_i = 1/n) y normalizar (Spinu 2013)."""
    S = cov.to_numpy()
    n = len(S)
    b = np.full(n, 1.0 / n)
    y0 = np.sqrt(b) / np.sqrt(np.diag(S))
    res = minimize(lambda y: 0.5 * y @ S @ y - b @ np.log(y), y0, jac=lambda y: S @ y - b / y,
                   method="L-BFGS-B", bounds=[(1e-12, None)] * n,
                   options={"maxiter": 10000, "ftol": 1e-16, "gtol": 1e-12})
    y = res.x if np.all(np.isfinite(res.x)) else y0
    return pd.Series(y / y.sum(), index=cov.index)


def _varianza_cluster(S: np.ndarray, idx: list[int]) -> float:
    sub = S[np.ix_(idx, idx)]
    ivp = 1.0 / np.diag(sub)
    ivp /= ivp.sum()
    return float(ivp @ sub @ ivp)


def hrp(cov: pd.DataFrame) -> pd.Series:
    """Hierarchical Risk Parity: agrupa por correlación (enlace simple sobre d = sqrt((1 - ρ) / 2)), ordena
    y reparte el peso por bisección recursiva en proporción inversa a la varianza de cada mitad."""
    S = cov.to_numpy()
    n = len(S)
    if n == 1:
        return pd.Series([1.0], index=cov.index)
    sd = np.sqrt(np.diag(S))
    corr = np.clip(S / np.outer(sd, sd), -1.0, 1.0)
    dist = np.sqrt(np.clip((1.0 - corr) / 2.0, 0.0, 1.0))
    np.fill_diagonal(dist, 0.0)
    orden = leaves_list(linkage(squareform(dist, checks=False), method="single")).tolist()
    w = np.ones(n)
    grupos = [orden]
    while grupos:
        grupos = [g[i:j] for g in grupos for i, j in ((0, len(g) // 2), (len(g) // 2, len(g))) if len(g) > 1]
        for k in range(0, len(grupos), 2):
            g1, g2 = grupos[k], grupos[k + 1]
            v1, v2 = _varianza_cluster(S, g1), _varianza_cluster(S, g2)
            alfa = 1.0 - v1 / (v1 + v2)
            w[g1] *= alfa
            w[g2] *= 1.0 - alfa
    return pd.Series(w / w.sum(), index=cov.index)


def orden_hrp(cov: pd.DataFrame) -> list[str]:
    """Orden de los activos según el agrupamiento jerárquico (para el mapa de correlaciones)."""
    S = cov.to_numpy()
    if len(S) < 3:
        return list(cov.index)
    sd = np.sqrt(np.diag(S))
    dist = np.sqrt(np.clip((1.0 - np.clip(S / np.outer(sd, sd), -1, 1)) / 2.0, 0.0, 1.0))
    np.fill_diagonal(dist, 0.0)
    return [cov.index[i] for i in leaves_list(linkage(squareform(dist, checks=False), method="single"))]


def frontera_eficiente(mu: pd.Series, cov: pd.DataFrame, peso_maximo: float = 1.0, puntos: int = 30
                       ) -> pd.DataFrame:
    """Puntos (retorno, volatilidad) de la frontera eficiente con las mismas restricciones."""
    mu = mu.reindex(cov.index)
    S, m = cov.to_numpy(), mu.to_numpy()
    n = len(S)
    tope = _tope(n, peso_maximo)
    w_mv = minima_varianza(cov, peso_maximo).to_numpy()
    r_min, r_max = float(m @ w_mv), float(m @ maximo_retorno_factible(mu, peso_maximo).to_numpy())
    filas, previo = [], w_mv
    for r in np.linspace(r_min, r_max, puntos):
        res = minimize(lambda w: w @ S @ w, previo, jac=lambda w: 2.0 * S @ w, method="SLSQP",
                       bounds=[(0.0, tope)] * n,
                       constraints=[_suma_uno(n), {"type": "eq", "fun": lambda w, r=r: m @ w - r,
                                                   "jac": lambda w: m}],
                       options={"maxiter": 1000, "ftol": 1e-14})
        if res.success:
            previo = np.clip(res.x, 0.0, None)
            filas.append({"retorno": float(m @ previo), "volatilidad": float(np.sqrt(previo @ S @ previo))})
    return pd.DataFrame(filas)


def contribuciones_riesgo(w: pd.Series, cov: pd.DataFrame) -> pd.Series:
    """Fracción del riesgo total que aporta cada activo: w_i (Σw)_i / (w'Σw)."""
    w = w.reindex(cov.index).fillna(0.0)
    S = cov.to_numpy()
    sw = S @ w.to_numpy()
    var = float(w.to_numpy() @ sw)
    return pd.Series(w.to_numpy() * sw / var, index=cov.index) if var > 0 else w * np.nan


def resumen(pesos: dict[str, pd.Series], mu: pd.Series, cov: pd.DataFrame, rf: float) -> pd.DataFrame:
    """Retorno esperado, volatilidad y Sharpe ex-ante (con el μ del modelo) y concentración de cada portafolio."""
    filas = {}
    for k, w in pesos.items():
        if w is None or w.empty:
            continue
        w = w.reindex(cov.index).fillna(0.0)
        r = float(w @ mu.reindex(cov.index).fillna(0.0))
        v = float(np.sqrt(w @ cov @ w))
        filas[NOMBRES.get(k, k)] = {
            "clave": k,
            "retorno_esperado": r,
            "volatilidad": v,
            "sharpe": (r - rf) / v if v > 0 else np.nan,
            "n_activos": int((w > 1e-9).sum()),
            "peso_maximo": float(w.max()),
            "n_efectivo": float(1.0 / (w ** 2).sum()),
            "top3": ", ".join(f"{s} {p:.0%}" for s, p in w.sort_values(ascending=False).head(3).items()),
        }
    return pd.DataFrame.from_dict(filas, orient="index")
