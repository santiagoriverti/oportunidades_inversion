"""Modelo de riesgo y retorno para optimizar portafolios (docs/METODOLOGIA.md §5).

- Retornos SEMANALES por defecto: BTC cotiza 7 días y los ETFs de Xetra cierran horas antes que Wall
  Street; con retornos diarios la correlación con EE.UU. sale artificialmente baja (XLK vs QDVE: 0,56
  diaria contra 0,92 semanal, medido el 2026-11-06) y el optimizador los usaría como falsos diversificadores.
- Covarianza con contracción de Ledoit-Wolf (estable aunque haya muchos activos y pocas semanas).
- Gemelos: activos con correlación semanal >= 0,99 y volatilidades parecidas (GLD/IAU, SPY/VOO/VTI...):
  se optimiza con uno solo (el de más historia) y los demás se muestran como equivalentes.
- Black-Litterman: equilibrio con pesos iguales + vistas proporcionales al score de oportunidad.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PERIODOS = {"D": 252, "W": 52}


def retornos(precios: pd.DataFrame, frecuencia: str = "W") -> pd.DataFrame:
    """Retornos simples diarios ("D") o semanales al viernes ("W")."""
    p = precios.resample("W-FRI").last() if frecuencia == "W" else precios
    return p.pct_change(fill_method=None).iloc[1:]


def seleccionar_ventana(precios: pd.DataFrame, anios: float, cobertura_minima: float,
                        fecha=None, recortar: bool = True) -> tuple[pd.DataFrame, dict[str, str]]:
    """Precios de la ventana [fecha - anios, fecha] de los activos con cobertura suficiente.

    Con ``recortar`` la ventana efectiva arranca cuando TODOS los incluidos tienen precio (covarianza con
    datos completos); sin recortar se devuelve la ventana completa (para sacar gemelos antes de recortar:
    si no, un gemelo joven como IBIT acortaría la ventana de todos aunque después se descarte).
    Devuelve (precios de la ventana, {activo excluido: motivo}).
    """
    if fecha is None:
        fin = precios.index.max()
    else:
        previas = precios.index[precios.index <= pd.Timestamp(fecha)]
        fin = previas[-1]
    inicio = fin - pd.Timedelta(days=int(round(anios * 365.25)))
    p = precios.loc[(precios.index > inicio) & (precios.index <= fin)]
    excluidos: dict[str, str] = {}
    cobertura = p.notna().mean()
    for s in p.columns:
        if cobertura[s] < cobertura_minima:
            excluidos[s] = (f"historia insuficiente en la ventana de {anios:g} años "
                            f"({cobertura[s]:.0%} de los días, mínimo {cobertura_minima:.0%})")
        elif pd.isna(p[s].iloc[-1]):
            excluidos[s] = "sin precio reciente (más de 5 días hábiles sin cotizar)"
    p = p[[s for s in p.columns if s not in excluidos]]
    if p.shape[1] == 0 or not recortar:
        return p, excluidos
    return recortar_inicio_comun(p), excluidos


def recortar_inicio_comun(p: pd.DataFrame) -> pd.DataFrame:
    """Recorta la ventana desde que todos los activos tienen precio y completa huecos internos con el último
    precio (la covarianza de Ledoit-Wolf necesita datos completos)."""
    if p.shape[1] == 0:
        return p
    inicio_ef = max(p[s].first_valid_index() for s in p.columns)
    return p.loc[p.index >= inicio_ef].ffill()


def grupos_gemelos(r_semanales: pd.DataFrame, umbral: float = 0.99, ratio_vol: float = 1.25,
                   historia: pd.Series | None = None, preferencia: list[str] | None = None) -> list[list[str]]:
    """Grupos de activos casi idénticos (correlación >= umbral y volatilidad a menos de ``ratio_vol`` veces).

    Cada grupo viene ordenado: primero el representante (el de más historia; desempata el orden de
    ``preferencia``, que suele ser el orden de la lista del usuario).
    """
    r = r_semanales.dropna(how="all")
    corr = r.corr(min_periods=26)
    vol = r.std()
    cols = list(r.columns)
    padre = {c: c for c in cols}

    def raiz(c):
        while padre[c] != c:
            padre[c] = padre[padre[c]]
            c = padre[c]
        return c

    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            rho = corr.at[a, b]
            va, vb = vol[a], vol[b]
            if pd.notna(rho) and rho >= umbral and va > 0 and vb > 0 and max(va, vb) / min(va, vb) <= ratio_vol:
                padre[raiz(a)] = raiz(b)
    grupos: dict[str, list[str]] = {}
    for c in cols:
        grupos.setdefault(raiz(c), []).append(c)
    orden = {c: i for i, c in enumerate(preferencia or cols)}
    hist = historia if historia is not None else pd.Series(0, index=cols)
    out = []
    for g in grupos.values():
        if len(g) > 1:
            out.append(sorted(g, key=lambda c: (-float(hist.get(c, 0) or 0), orden.get(c, 10 ** 6), c)))
    return sorted(out, key=lambda g: orden.get(g[0], 10 ** 6))


def covarianza(r: pd.DataFrame, periodos: int) -> tuple[pd.DataFrame, float]:
    """Covarianza anualizada con contracción de Ledoit-Wolf. Devuelve (matriz, intensidad de contracción)."""
    from sklearn.covariance import LedoitWolf

    X = r.dropna(how="any")
    if len(X) < 10:
        raise ValueError(f"Muy pocas observaciones completas ({len(X)}) para estimar la covarianza")
    lw = LedoitWolf().fit(X.to_numpy())
    cov = pd.DataFrame(lw.covariance_ * periodos, index=r.columns, columns=r.columns)
    return cov, float(lw.shrinkage_)


def cagr_por_columna(r: pd.DataFrame, periodos: int) -> pd.Series:
    n = r.notna().sum()
    total = (1.0 + r.fillna(0.0)).prod()
    return total.clip(lower=1e-12) ** (periodos / n.where(n > 0)) - 1.0


def retornos_esperados(r: pd.DataFrame, metodo: str, periodos: int, rf: float,
                       r_bench: pd.Series | None = None) -> pd.Series:
    """Retorno anual esperado de cada activo.

    - "historico": CAGR de la ventana (crecimiento compuesto; penaliza la volatilidad más que la media
      aritmética).
    - "capm": rf + beta * (CAGR del benchmark - rf), con beta estimada en la misma ventana.
    """
    if metodo == "historico":
        return cagr_por_columna(r, periodos)
    if metodo == "capm":
        if r_bench is None:
            raise ValueError("El método CAPM necesita los retornos del benchmark")
        m = r_bench.reindex(r.index)
        mu_m = cagr_por_columna(m.to_frame("m"), periodos)["m"]
        var_m = m.var()
        betas = r.apply(lambda c: c.cov(m) / var_m if var_m > 0 else np.nan)
        return rf + betas * (mu_m - rf)
    raise ValueError(f"metodo_retornos desconocido: {metodo}")


def aversion_riesgo(r_bench: pd.Series, rf: float, periodos: int) -> float:
    """Delta de Black-Litterman: (retorno del benchmark - rf) / varianza, acotado a [1, 6]; 2,5 si no
    tiene sentido (por ejemplo, si el benchmark rindió menos que la tasa libre de riesgo)."""
    m = pd.Series(r_bench).dropna()
    if len(m) < 20:
        return 2.5
    mu = cagr_por_columna(m.to_frame("m"), periodos)["m"]
    var = m.var() * periodos
    delta = (mu - rf) / var if var > 0 else np.nan
    if not np.isfinite(delta) or delta <= 0:
        return 2.5
    return float(np.clip(delta, 1.0, 6.0))


def black_litterman(cov: pd.DataFrame, rf: float, delta: float, score: pd.Series, tau: float = 0.05,
                    intensidad: float = 0.25, pesos_previos: pd.Series | None = None
                    ) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Retornos esperados de Black-Litterman con vistas tomadas del score de oportunidad.

    - Equilibrio (previa): Π = δ Σ w, con w = pesos iguales (neutral: no hay capitalizaciones comparables
      entre acciones, ETFs y cripto).
    - Vista absoluta por activo con score: q_i = Π_i + intensidad · z_i · σ_i, con z_i = (score - 50) / 50
      en [-1, 1]: un score de 100 suma ``intensidad`` de Sharpe; uno de 0 la resta.
    - Confianza de He-Litterman: Ω = diag(τ P Σ P').
    Devuelve (posterior, previa, vistas), todos como retorno total anual (incluyen rf).
    """
    activos = cov.index
    n = len(activos)
    S = cov.to_numpy()
    w = (pesos_previos.reindex(activos).fillna(0.0).to_numpy() if pesos_previos is not None
         else np.full(n, 1.0 / n))
    pi = delta * S @ w
    z = ((score.reindex(activos).astype(float) - 50.0) / 50.0).clip(-1.0, 1.0)
    con = z.notna().to_numpy()
    if not con.any():
        previa = pd.Series(pi + rf, index=activos)
        return previa, previa, pd.Series(dtype=float)
    vol = np.sqrt(np.diag(S))
    P = np.eye(n)[con]
    q = pi[con] + intensidad * z.to_numpy()[con] * vol[con]
    tS = tau * S
    PtSP = P @ tS @ P.T
    omega = np.diag(np.diag(PtSP))
    M = tS @ P.T @ np.linalg.inv(PtSP + omega)
    post = pi + M @ (q - P @ pi)
    return (pd.Series(post + rf, index=activos), pd.Series(pi + rf, index=activos),
            pd.Series(q + rf, index=activos[con]))
