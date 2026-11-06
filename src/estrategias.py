"""Arma TODOS los portafolios a una fecha con los datos disponibles hasta esa fecha.

Lo usan el análisis de hoy (pipeline.Analisis.optimizar) y el backtest (backtest.correr_backtest): así el
backtest prueba exactamente la misma lógica que se recomienda hoy, sin mirar el futuro.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import portafolios as P
from . import riesgo


def armar_portafolios(precios: pd.DataFrame, candidatos: list[str], cfg, rf: float, fecha=None,
                      score: pd.Series | None = None, top: list[str] | None = None,
                      benchmark: str | None = None, preferencia: list[str] | None = None,
                      calcular_frontera: bool = False) -> dict:
    """Devuelve un diccionario con:
        pesos       {clave: Serie de pesos} (claves de portafolios.NOMBRES; None si no se pudo armar)
        mu, cov     retornos esperados y covarianza anual de los activos optimizables
        mu_bl, pi   retornos de Black-Litterman (posterior y equilibrio)
        excluidos   {activo: motivo} (historia insuficiente, sin precio reciente, gemelo)
        gemelos     [[representante, equivalentes...], ...]
        ventana     (inicio, fin, observaciones)
        notas       {clave: nota del optimizador}
        frontera    DataFrame (retorno, volatilidad) si calcular_frontera
        shrinkage   intensidad de Ledoit-Wolf
    """
    fecha = precios.index.max() if fecha is None else pd.Timestamp(fecha)
    hist = precios.loc[:fecha]
    cands = [c for c in dict.fromkeys(candidatos) if c in hist.columns]
    p_v, excluidos = riesgo.seleccionar_ventana(hist[cands], cfg.ventana_anios, cfg.cobertura_minima,
                                                recortar=False)
    gemelos: list[list[str]] = []
    if cfg.deduplicar and p_v.shape[1] > 1:
        r_sem = riesgo.retornos(p_v, "W")
        historia = hist[p_v.columns].notna().sum()
        gemelos = riesgo.grupos_gemelos(r_sem, cfg.umbral_gemelos, cfg.ratio_vol_gemelos, historia,
                                        preferencia or cands)
        for g in gemelos:
            for s in g[1:]:
                excluidos[s] = f"gemelo de {g[0]} (se optimiza con {g[0]})"
        p_v = p_v.drop(columns=[s for g in gemelos for s in g[1:]])
    p_v = riesgo.recortar_inicio_comun(p_v)
    activos = list(p_v.columns)
    salida = {"pesos": {k: None for k in P.NOMBRES}, "excluidos": excluidos, "gemelos": gemelos, "notas": {},
              "mu": pd.Series(dtype=float), "cov": pd.DataFrame(), "mu_bl": pd.Series(dtype=float),
              "pi": pd.Series(dtype=float), "frontera": None, "shrinkage": np.nan,
              "ventana": (p_v.index.min() if len(p_v) else None, p_v.index.max() if len(p_v) else None, len(p_v))}
    if len(activos) < 2:
        salida["notas"]["general"] = "menos de 2 activos optimizables: no se arman portafolios"
        return salida

    periodos = riesgo.PERIODOS[cfg.frecuencia_riesgo]
    r = riesgo.retornos(p_v, cfg.frecuencia_riesgo)
    cov, shrink = riesgo.covarianza(r, periodos)
    r_bench = None
    if benchmark and benchmark in hist.columns:
        pb = hist[benchmark].loc[p_v.index.min():p_v.index.max()]
        r_bench = riesgo.retornos(pb.to_frame(), cfg.frecuencia_riesgo)[benchmark].reindex(r.index)
    mu = riesgo.retornos_esperados(r, cfg.metodo_retornos, periodos, rf, r_bench)
    if mu.isna().any():
        mu = mu.fillna(mu.median())
    salida.update(mu=mu, cov=cov, shrinkage=shrink)
    wmax, wmin = cfg.peso_maximo, cfg.peso_minimo
    pesos, notas = {}, {}

    pesos["pesos_iguales"] = P.pesos_iguales(activos)
    pesos["minima_varianza"] = P.minima_varianza(cov, wmax)
    pesos["maximo_sharpe"], notas["maximo_sharpe"] = P.maximo_sharpe(mu, cov, rf, wmax)
    pesos["volatilidad_objetivo"], notas["volatilidad_objetivo"] = P.volatilidad_objetivo(
        mu, cov, cfg.volatilidad_objetivo, wmax)
    pesos["paridad_riesgo"] = P.paridad_riesgo(cov)
    pesos["hrp"] = P.hrp(cov)

    if score is not None and score.reindex(activos).notna().any():
        delta = riesgo.aversion_riesgo(r_bench if r_bench is not None else r.mean(axis=1), rf, periodos)
        mu_bl, pi, _ = riesgo.black_litterman(cov, rf, delta, score, cfg.bl_tau, cfg.bl_intensidad)
        pesos["black_litterman"], notas["black_litterman"] = P.maximo_sharpe(mu_bl, cov, rf, wmax)
        salida.update(mu_bl=mu_bl, pi=pi)
    else:
        notas["black_litterman"] = "sin score de oportunidad: no se arma"

    if top:
        sel = [s for s in top if s in activos]
        # los gemelos excluidos se reemplazan por su representante
        for g in gemelos:
            if any(s in top for s in g[1:]) and g[0] not in sel and g[0] in activos:
                sel.append(g[0])
        if len(sel) >= 2:
            pesos["oportunidades"] = P.paridad_riesgo(cov.loc[sel, sel])
        else:
            notas["oportunidades"] = "menos de 2 oportunidades optimizables: no se arma"
    else:
        notas["oportunidades"] = "no hay oportunidades detectadas: no se arma"

    for k, w in list(pesos.items()):
        if k == "pesos_iguales":
            continue
        minimo = wmin if k in P.CONCENTRADOS else 0.0
        pesos[k] = P.limpiar_pesos(w, minimo, wmax)
    salida["pesos"].update(pesos)
    salida["notas"] = {k: v for k, v in notas.items() if v}
    if calcular_frontera:
        try:
            salida["frontera"] = P.frontera_eficiente(mu, cov, wmax)
        except Exception as e:  # noqa: BLE001 - la frontera es solo un gráfico
            salida["notas"]["frontera"] = f"no se pudo calcular la frontera ({type(e).__name__})"
    return salida
