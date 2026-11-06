"""Indicadores técnicos y estadísticos de "precio artificialmente bajo".

Todo se calcula como PANEL (fecha x activo) con ventanas que miran solo hacia atrás: el análisis de hoy toma
la última fila y el backtest toma la fila de cada fecha de rebalanceo (sin mirar el futuro). Fórmulas en
docs/METODOLOGIA.md §2. Ventanas en días hábiles: 21 = 1 mes, 63 = 3 meses, 252 = 1 año, 756 = 3 años.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DIAS_ANIO = 252


def _como_df(p):
    if isinstance(p, pd.Series):
        return p.to_frame(p.name if p.name is not None else "x"), True
    return p, False


def _volver(df, era_serie):
    return df.iloc[:, 0] if era_serie else df


def sma(p, n: int):
    return p.rolling(n, min_periods=n).mean()


def distancia_sma(p, n: int):
    """Precio / media móvil simple de n días - 1 (negativo = debajo de la media)."""
    return p / sma(p, n) - 1.0


def zscore_log(p, n: int):
    """(log precio - media de n días del log precio) / desvío de n días."""
    lp = np.log(p)
    m = lp.rolling(n, min_periods=n).mean()
    s = lp.rolling(n, min_periods=n).std()
    return (lp - m) / s.where(s > 0)


def posicion_rango(p, n: int):
    """Ubicación del precio en el rango mínimo-máximo de n días (0 = en el mínimo, 1 = en el máximo)."""
    lo = p.rolling(n, min_periods=n).min()
    hi = p.rolling(n, min_periods=n).max()
    rango = hi - lo
    return (p - lo) / rango.where(rango > 0)


def drawdown_rolling(p, n: int):
    """Caída desde el máximo de los últimos n días (0 = en el máximo, -0,30 = 30% abajo)."""
    return p / p.rolling(n, min_periods=n).max() - 1.0


def drawdown_historico(p):
    """Caída desde el máximo de toda la historia disponible."""
    return p / p.cummax() - 1.0


def rsi(p, n: int = 14):
    """RSI de Wilder (media exponencial con alfa = 1/n): 100 * suba media / (suba media + baja media)."""
    d = p.diff()
    sube = d.clip(lower=0)
    baja = (-d).clip(lower=0)
    m_sube = sube.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    m_baja = baja.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    total = m_sube + m_baja
    return 100.0 * m_sube / total.where(total > 0)


def bollinger_pctb(p, n: int = 20, k: float = 2.0):
    """%B de Bollinger: 0 = banda inferior (media - k desvíos), 1 = banda superior; < 0 = debajo de la banda."""
    m = p.rolling(n, min_periods=n).mean()
    s = p.rolling(n, min_periods=n).std()
    ancho = 2.0 * k * s
    return (p - (m - k * s)) / ancho.where(ancho > 0)


def retorno(p, n: int):
    """Retorno de los últimos n días."""
    return p / p.shift(n) - 1.0


def zscore_retorno(p, n: int, historia: int):
    """Qué tan inusual es el retorno de n días comparado con los retornos de n días de los últimos
    ``historia`` días del mismo activo (en desvíos)."""
    r = retorno(p, n)
    m = r.rolling(historia, min_periods=historia // 2).mean()
    s = r.rolling(historia, min_periods=historia // 2).std()
    return (r - m) / s.where(s > 0)


def zscore_relativo(p, bench: pd.Series, n: int):
    """z-score del log del precio relativo al benchmark (activo / SPY): negativo = rinde por debajo de lo
    normal contra el mercado."""
    return zscore_log(p.div(bench, axis=0), n)


def volatilidad(p, n: int):
    """Volatilidad anualizada de los retornos logarítmicos diarios de los últimos n días."""
    return np.log(p).diff().rolling(n, min_periods=n).std() * np.sqrt(DIAS_ANIO)


def z_tendencia(p, n: int = 756):
    """Desvío del log precio respecto de su tendencia lineal de n días, en desvíos de los residuos.

    Regresión móvil log(P) = a + b·t con sumas móviles (equivale a un ``polyfit`` en cada ventana).
    Negativo = el precio está debajo de su senda de crecimiento de los últimos n días.
    """
    y, era_serie = _como_df(np.log(p))
    t = pd.DataFrame(np.repeat(np.arange(len(y), dtype=float)[:, None], y.shape[1], axis=1),
                     index=y.index, columns=y.columns).where(y.notna())

    def suma(x):
        return x.rolling(n, min_periods=n).sum()

    sx, sy, sxx, sxy, syy = suma(t), suma(y), suma(t * t), suma(t * y), suma(y * y)
    den = n * sxx - sx * sx
    b = (n * sxy - sx * sy) / den.where(den > 0)
    a = (sy - b * sx) / n
    sse = (syy - a * sy - b * sxy).clip(lower=0)
    s = np.sqrt(sse / (n - 2))
    z = (y - (a + b * t)) / s.where(s > 0)
    return _volver(z, era_serie)


def media_vida(residuos: pd.Series) -> float:
    """Media vida (días) de un proceso que revierte a la media (Ornstein-Uhlenbeck discreto):
    Δe_t = α + β·e_{t-1}; media vida = -ln 2 / ln(1 + β). NaN si no revierte (β >= 0)."""
    e = pd.Series(residuos).dropna()
    if len(e) < 60:
        return np.nan
    de = e.diff().iloc[1:].to_numpy()
    el = e.shift(1).iloc[1:].to_numpy()
    X = np.column_stack([np.ones_like(el), el])
    beta = np.linalg.lstsq(X, de, rcond=None)[0][1]
    if not -1.0 < beta < 0.0:
        return np.nan
    return float(-np.log(2.0) / np.log1p(beta))


def hurst(serie_log: pd.Series, max_lag: int = 100) -> float:
    """Exponente de Hurst por la varianza de las diferencias a distintos rezagos: desvío(x_{t+τ} - x_t) ∝ τ^H.
    H ≈ 0,5 paseo aleatorio; H < 0,5 tiende a revertir; H > 0,5 tiende a seguir la tendencia."""
    x = np.asarray(pd.Series(serie_log).dropna(), dtype=float)
    if len(x) < 200:
        return np.nan
    tope = max(min(max_lag, len(x) // 4), 10)
    lags = np.unique(np.logspace(np.log10(2), np.log10(tope), 20).astype(int))
    tau = np.array([np.std(x[lag:] - x[:-lag]) for lag in lags])
    ok = tau > 0
    if ok.sum() < 5:
        return np.nan
    return float(np.polyfit(np.log(lags[ok]), np.log(tau[ok]), 1)[0])


def panel_indicadores(precios: pd.DataFrame, benchmark: str | None = None) -> dict[str, pd.DataFrame]:
    """Todos los indicadores como paneles fecha x activo (precios diarios en USD, días hábiles)."""
    p = precios.astype(float)
    s50, s200 = sma(p, 50), sma(p, 200)
    paneles = {
        "precio": p,
        "ret_1m": retorno(p, 21),
        "ret_3m": retorno(p, 63),
        "ret_6m": retorno(p, 126),
        "ret_12m": retorno(p, 252),
        "dist_sma50": p / s50 - 1.0,
        "dist_sma200": p / s200 - 1.0,
        "zscore_1a": zscore_log(p, 252),
        "z_tendencia_3a": z_tendencia(p, 756),
        "posicion_52s": posicion_rango(p, 252),
        "drawdown_52s": drawdown_rolling(p, 252),
        "drawdown_max": drawdown_historico(p),
        "rsi_14": rsi(p, 14),
        "bollinger_pctb": bollinger_pctb(p, 20, 2.0),
        "z_ret_3m": zscore_retorno(p, 63, 756),
        "vol_1m": volatilidad(p, 21),
        "vol_1a": volatilidad(p, 252),
        "tendencia_alcista": (s50 > s200).astype(float).where(s200.notna()),
        "dias_historia": p.notna().cumsum().where(p.notna()),
    }
    if benchmark is not None and benchmark in p.columns:
        paneles["z_relativo_bench"] = zscore_relativo(p, p[benchmark], 252)
    else:
        paneles["z_relativo_bench"] = p * np.nan
    paneles["ratio_vol"] = paneles["vol_1m"] / paneles["vol_1a"]
    return paneles


def foto(paneles: dict[str, pd.DataFrame], fecha=None) -> pd.DataFrame:
    """Indicadores de cada activo a una fecha (la última disponible <= fecha; por defecto, la última)."""
    idx = paneles["precio"].index
    if fecha is None:
        f = idx[-1]
    else:
        previas = idx[idx <= pd.Timestamp(fecha)]
        if len(previas) == 0:
            raise ValueError(f"No hay datos antes de {fecha}")
        f = previas[-1]
    df = pd.DataFrame({k: v.loc[f] for k, v in paneles.items()})
    df.index.name = "activo"
    return df


def reversion_media(precios: pd.DataFrame, n: int = 756, fecha=None) -> pd.DataFrame:
    """Diagnóstico de reversión a la media de cada activo con los últimos n días (hasta ``fecha``):
    media vida de los desvíos respecto de la tendencia lineal y exponente de Hurst del log precio."""
    p = precios if fecha is None else precios.loc[: pd.Timestamp(fecha)]
    filas = {}
    for s in p.columns:
        lp = np.log(p[s].dropna().iloc[-n:])
        if len(lp) < 200:
            filas[s] = {"media_vida_dias": np.nan, "hurst": np.nan}
            continue
        t = np.arange(len(lp), dtype=float)
        b, a = np.polyfit(t, lp.to_numpy(), 1)
        resid = pd.Series(lp.to_numpy() - (a + b * t), index=lp.index)
        filas[s] = {"media_vida_dias": media_vida(resid), "hurst": hurst(lp)}
    df = pd.DataFrame.from_dict(filas, orient="index")
    df.index.name = "activo"
    return df
