"""Backtest walk-forward de todas las estrategias (docs/METODOLOGIA.md §7).

En cada fecha de rebalanceo t (fin de mes, trimestre o semestre):
1. indicadores y score con datos hasta t (sin fundamentales: Yahoo no da su historia);
2. portafolios con estrategias.armar_portafolios(precios hasta t) -> la misma lógica que hoy;
3. se mantienen (comprar y mantener, los pesos derivan) hasta el próximo rebalanceo;
4. al rebalancear se descuenta costo_bps por cada unidad de rotación (Σ|w_nuevo - w_derivado|).

Además mide si el score predijo algo: correlación de rangos (IC de Spearman) entre el score en t y el
retorno hasta el próximo rebalanceo, y el exceso de las oportunidades contra el promedio del universo.

Sesgos a tener en cuenta (se muestran en el notebook): el universo se eligió HOY (sesgo de supervivencia:
no están los que quebraron o se dejaron de mirar) y no hay fundamentales históricos.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from . import indicadores, metricas, senales
from .estrategias import armar_portafolios
from .portafolios import NOMBRES


def fechas_rebalanceo(indice: pd.DatetimeIndex, inicio, frecuencia: str = "Q") -> list[pd.Timestamp]:
    """Último día hábil de cada mes ("M"), trimestre ("Q") o semestre ("S") desde ``inicio``. Excluye el
    último día de datos (no habría período de tenencia)."""
    idx = indice[indice >= pd.Timestamp(inicio)]
    if len(idx) == 0:
        return []
    if frecuencia == "M":
        clave = idx.year * 12 + idx.month
    elif frecuencia == "Q":
        clave = idx.year * 4 + (idx.month - 1) // 3
    elif frecuencia == "S":
        clave = idx.year * 2 + (idx.month - 1) // 6
    else:
        raise ValueError(f"frecuencia de rebalanceo desconocida: {frecuencia}")
    ultimos = pd.Series(idx, index=idx).groupby(np.asarray(clave)).max()
    fechas = [pd.Timestamp(f) for f in ultimos.tolist()]
    return [f for f in fechas if f < indice.max()]


def correr_backtest(precios: pd.DataFrame, candidatos: list[str], cfg, rf: float, benchmark: str,
                    preferencia: list[str] | None = None, mostrar_progreso: bool = True) -> dict:
    """Corre el backtest. ``precios``: diarios en USD (días hábiles) de candidatos + benchmark.

    Devuelve dict con: retornos (DataFrame diario por estrategia + benchmark), metricas (tabla),
    pesos (DataFrame largo fecha/estrategia/activo/peso), ic (DataFrame por fecha), rotacion (por estrategia)
    y fechas.
    """
    t0 = time.time()
    cols = list(dict.fromkeys([c for c in candidatos if c in precios.columns] +
                              ([benchmark] if benchmark in precios.columns else [])))
    p = precios[cols]
    paneles = indicadores.panel_indicadores(p, benchmark)
    inicio = p.index.min() + pd.Timedelta(days=int(round(cfg.ventana_anios * 365.25)))
    fechas = fechas_rebalanceo(p.index, inicio, cfg.rebalanceo)
    if len(fechas) < 2:
        raise ValueError("No alcanza la historia para el backtest: subí anios_historia o bajá ventana_anios")
    claves = list(NOMBRES)
    rets = {k: [] for k in claves}
    deriva = {k: None for k in claves}
    rotacion = {k: [] for k in claves}
    filas_pesos, filas_ic = [], []
    cands = [c for c in candidatos if c in p.columns]
    for i, t in enumerate(fechas):
        t_sig = fechas[i + 1] if i + 1 < len(fechas) else p.index.max()
        f = indicadores.foto(paneles, t).loc[cands]
        tabla = senales.calcular_score(f, None, cfg.pesos_grupos, cfg.umbrales_senales,
                                       cfg.umbral_score_oportunidad, cfg.min_senales_oportunidad)
        top = senales.top_oportunidades(tabla, cfg.top_n_oportunidades)
        res = armar_portafolios(p, cands, cfg, rf, fecha=t, score=tabla["score"], top=top,
                                benchmark=benchmark, preferencia=preferencia)
        tramo = p.loc[t:t_sig].ffill()
        rel = tramo / tramo.iloc[0]
        for k in claves:
            w = res["pesos"].get(k)
            if w is None or w.empty:
                deriva[k] = None
                continue
            w = w[w > 0]
            valor = (rel[w.index] * w.to_numpy()).sum(axis=1)
            r = valor.pct_change().iloc[1:]
            if deriva[k] is not None:
                todos = w.index.union(deriva[k].index)
                rot = float((w.reindex(todos).fillna(0) - deriva[k].reindex(todos).fillna(0)).abs().sum())
                rotacion[k].append(rot)
                if len(r):
                    r.iloc[0] -= cfg.costo_bps / 1e4 * rot
            rets[k].append(r)
            fin = w * rel[w.index].iloc[-1]
            deriva[k] = fin / fin.sum()
            for s, v in w.items():
                filas_pesos.append({"fecha": t, "estrategia": k, "activo": s, "peso": float(v)})
        # ¿El score predijo el retorno del período siguiente?
        fwd = (p.loc[t_sig, cands] / p.loc[t, cands] - 1.0).astype(float)
        sc = tabla["score"].reindex(cands)
        ok = sc.notna() & fwd.notna()
        if ok.sum() >= 5 and fwd[ok].std() > 0 and sc[ok].std() > 0:
            filas_ic.append({
                "fecha": t, "fin": t_sig, "n": int(ok.sum()),
                "ic_spearman": float(sc[ok].rank().corr(fwd[ok].rank())),
                "ret_oportunidades": float(fwd.reindex(top).mean()) if top else np.nan,
                "ret_universo": float(fwd[ok].mean()),
            })
        if mostrar_progreso and (i % 5 == 4 or i == len(fechas) - 1):
            print(f"  rebalanceo {i + 1}/{len(fechas)}: {t.date()} ({time.time() - t0:.0f}s)")
    # Un período en que una estrategia no se pudo armar queda en efectivo (retorno 0)
    retornos = pd.DataFrame({k: pd.concat(v) for k, v in rets.items() if v}).fillna(0.0)
    if benchmark in p.columns:
        rb = p[benchmark].pct_change(fill_method=None)
        retornos[benchmark] = rb.reindex(retornos.index)
    retornos = retornos.sort_index()
    retornos = retornos[~retornos.index.duplicated()]
    filas = {}
    for k in retornos.columns:
        m = metricas.resumen_serie(retornos[k], rf, 252)
        m["rotacion_media"] = float(np.mean(rotacion[k])) if k in rotacion and rotacion[k] else 0.0
        filas[NOMBRES.get(k, f"Benchmark ({k})")] = m
    tabla_m = pd.DataFrame.from_dict(filas, orient="index")
    if benchmark in retornos.columns:
        bench_m = metricas.cagr(retornos[benchmark], 252)
        tabla_m["exceso_vs_benchmark"] = tabla_m["retorno_anual"] - bench_m
    ic = pd.DataFrame(filas_ic)
    if not ic.empty:
        ic["exceso_oportunidades"] = ic["ret_oportunidades"] - ic["ret_universo"]
    return {"retornos": retornos, "metricas": tabla_m.sort_values("sharpe", ascending=False),
            "pesos": pd.DataFrame(filas_pesos), "ic": ic, "fechas": fechas,
            "rotacion": {k: v for k, v in rotacion.items() if v}, "segundos": time.time() - t0}


def resumen_ic(ic: pd.DataFrame) -> dict:
    """Resumen de la capacidad predictiva del score en el backtest."""
    if ic is None or ic.empty:
        return {}
    x = ic["ic_spearman"].dropna()
    t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std(ddof=1) > 0 else np.nan
    return {
        "periodos": int(len(x)),
        "ic_medio": float(x.mean()),
        "ic_t_stat": float(t),
        "pct_ic_positivo": float((x > 0).mean()),
        "exceso_medio_oportunidades": float(ic["exceso_oportunidades"].mean()),
        "pct_periodos_oportunidades_ganan": float((ic["exceso_oportunidades"] > 0).mean()),
    }
