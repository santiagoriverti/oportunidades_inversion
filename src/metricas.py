"""Métricas de riesgo y performance de una serie de retornos (activo, portafolio o estrategia).

Convenciones (docs/METODOLOGIA.md §4):
- Retornos simples por período; ``periodos`` = 252 (diarios) o 52 (semanales) por año.
- Sharpe y Sortino con la media ARITMÉTICA del exceso sobre la tasa libre de riesgo (Sharpe 1994),
  anualizados; la tasa anual se pasa a la del período con (1 + rf)^(1/periodos) - 1.
- Retorno anual = CAGR (crecimiento compuesto efectivo).
- VaR y CVaR históricos al 95%, de un período, expresados como pérdida positiva.
- Beta y alfa de Jensen contra el benchmark; para activos de otras bolsas usar retornos semanales
  (los diarios subestiman la correlación por la diferencia de horarios).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


EPS_VOL = 1e-12  # desvíos menores son ruido de punto flotante (serie constante): Sharpe no definido


def tasa_periodo(rf_anual: float, periodos: int) -> float:
    return (1.0 + rf_anual) ** (1.0 / periodos) - 1.0


def cagr(r: pd.Series, periodos: int = 252) -> float:
    r = pd.Series(r).dropna()
    if r.empty:
        return np.nan
    total = float((1.0 + r).prod())
    if total <= 0:
        return -1.0
    return total ** (periodos / len(r)) - 1.0


def volatilidad(r: pd.Series, periodos: int = 252) -> float:
    r = pd.Series(r).dropna()
    return float(r.std(ddof=1) * np.sqrt(periodos)) if len(r) > 1 else np.nan


def sharpe(r: pd.Series, rf_anual: float = 0.0, periodos: int = 252) -> float:
    r = pd.Series(r).dropna()
    if len(r) < 2:
        return np.nan
    ex = r - tasa_periodo(rf_anual, periodos)
    s = r.std(ddof=1)
    return float(ex.mean() * periodos / (s * np.sqrt(periodos))) if s > EPS_VOL else np.nan


def sortino(r: pd.Series, rf_anual: float = 0.0, periodos: int = 252) -> float:
    r = pd.Series(r).dropna()
    if len(r) < 2:
        return np.nan
    ex = r - tasa_periodo(rf_anual, periodos)
    abajo = np.sqrt(np.mean(np.minimum(ex, 0.0) ** 2)) * np.sqrt(periodos)
    return float(ex.mean() * periodos / abajo) if abajo > EPS_VOL else np.nan


def max_drawdown(r: pd.Series) -> float:
    """Peor caída desde un máximo (negativa: -0,35 = cayó 35%)."""
    r = pd.Series(r).dropna()
    if r.empty:
        return np.nan
    riqueza = np.concatenate([[1.0], (1.0 + r).cumprod().to_numpy()])
    pico = np.maximum.accumulate(riqueza)
    return float((riqueza / pico - 1.0).min())


def calmar(r: pd.Series, periodos: int = 252) -> float:
    mdd = max_drawdown(r)
    return float(cagr(r, periodos) / abs(mdd)) if mdd and mdd < 0 else np.nan


def var_historico(r: pd.Series, nivel: float = 0.95) -> float:
    r = pd.Series(r).dropna()
    return float(-np.quantile(r, 1.0 - nivel)) if len(r) >= 20 else np.nan


def cvar_historico(r: pd.Series, nivel: float = 0.95) -> float:
    r = pd.Series(r).dropna()
    if len(r) < 20:
        return np.nan
    q = np.quantile(r, 1.0 - nivel)
    return float(-r[r <= q].mean())


def beta_alfa(r: pd.Series, r_bench: pd.Series, rf_anual: float = 0.0, periodos: int = 52) -> tuple[float, float,
                                                                                                     float]:
    """(beta, alfa de Jensen anualizado, correlación) con las fechas en común."""
    df = pd.concat([pd.Series(r), pd.Series(r_bench)], axis=1).dropna()
    if len(df) < 20:
        return np.nan, np.nan, np.nan
    rf_p = tasa_periodo(rf_anual, periodos)
    a, m = df.iloc[:, 0] - rf_p, df.iloc[:, 1] - rf_p
    var_m = m.var(ddof=1)
    if var_m <= 0:
        return np.nan, np.nan, np.nan
    beta = float(a.cov(m) / var_m)
    alfa = float((a.mean() - beta * m.mean()) * periodos)
    return beta, alfa, float(df.iloc[:, 0].corr(df.iloc[:, 1]))


def resumen_serie(r: pd.Series, rf_anual: float = 0.0, periodos: int = 252) -> dict:
    """Métricas principales de una serie de retornos."""
    r = pd.Series(r).dropna()
    return {
        "retorno_anual": cagr(r, periodos),
        "volatilidad": volatilidad(r, periodos),
        "sharpe": sharpe(r, rf_anual, periodos),
        "sortino": sortino(r, rf_anual, periodos),
        "max_drawdown": max_drawdown(r),
        "calmar": calmar(r, periodos),
        "var_95": var_historico(r),
        "cvar_95": cvar_historico(r),
        "asimetria": float(r.skew()) if len(r) > 2 else np.nan,
        "curtosis": float(r.kurt()) if len(r) > 3 else np.nan,
        "retorno_total": float((1.0 + r).prod() - 1.0) if len(r) else np.nan,
        "periodos": int(len(r)),
    }


def tabla_metricas_activos(precios: pd.DataFrame, inicio, rf_anual: float, benchmark: str | None) -> pd.DataFrame:
    """Métricas de cada activo en la ventana [inicio, fin]: diarias para riesgo/retorno y semanales para
    beta, alfa y correlación con el benchmark."""
    p = precios.loc[precios.index >= pd.Timestamp(inicio)]
    rd = p.pct_change(fill_method=None)
    rs = p.resample("W-FRI").last().pct_change(fill_method=None)
    rb = rs[benchmark] if benchmark and benchmark in rs.columns else None
    filas = {}
    for s in p.columns:
        serie = rd[s].dropna()
        if len(serie) < 20:
            continue
        fila = resumen_serie(serie, rf_anual, 252)
        fila["dias"] = fila.pop("periodos")
        if rb is not None:
            fila["beta"], fila["alfa"], fila["correlacion_bench"] = beta_alfa(rs[s], rb, rf_anual, 52)
        filas[s] = fila
    df = pd.DataFrame.from_dict(filas, orient="index")
    df.index.name = "activo"
    return df
