"""Seguimiento ex-post: ¿cómo les fue a los portafolios y a las señales de cada corrida guardada?

Para cada corrida (docs/METODOLOGIA.md §8):
- Base = cierre de la ``fecha_datos`` de la corrida, tomado de una descarga NUEVA de precios ajustados
  (Yahoo reajusta hacia atrás con cada dividendo: nunca se mezclan precios bajados en días distintos).
- Cada portafolio se "compra" en la base con sus pesos y se mantiene (los pesos derivan).
- Se compara contra el benchmark en el mismo período y a plazos fijos (1, 3, 6, 12 meses).
- Señales: retorno de cada activo desde la base; promedio por clasificación, IC de Spearman entre score y
  retorno, y % de "Oportunidad" que le ganaron al benchmark.
Retorno anualizado, volatilidad y Sharpe solo con 63 días hábiles o más (con menos no significan nada).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import datos, metricas
from .portafolios import NOMBRES

MIN_DIAS_ANUALIZAR = 63


def simbolos_de_corridas(corridas: list[dict], benchmark: str) -> list[str]:
    s = set()
    for c in corridas:
        for w in c["pesos"].values():
            s.update(w.index)
        s.update(c["senales"].index)
        s.add(c["metadata"].get("benchmark", benchmark))
    s.add(benchmark)
    return sorted(x for x in s if isinstance(x, str) and x)


def descargar_precios_corridas(corridas: list[dict], benchmark: str = "SPY") -> tuple[pd.DataFrame, list[str]]:
    """Precios ajustados en USD (días hábiles) desde la corrida más vieja hasta hoy. Devuelve (precios, avisos)."""
    if not corridas:
        return pd.DataFrame(), []
    inicio = min(pd.Timestamp(c["metadata"]["fecha_datos"]) for c in corridas) - pd.Timedelta(days=15)
    simbolos = simbolos_de_corridas(corridas, benchmark)
    monedas = {}
    for c in corridas:
        monedas.update(c["metadata"].get("monedas", {}))
    crudos, faltan = datos.descargar_cierres(simbolos, inicio)
    avisos = [f"Sin precios para: {', '.join(faltan)}"] if faltan else []
    p = datos.alinear_dias_habiles(crudos)
    mon = datos.detectar_monedas(list(p.columns), monedas)
    p, av = datos.convertir_a_usd(p, mon, inicio)
    return p, avisos + av


def _curva(precios: pd.DataFrame, pesos: pd.Series, base) -> tuple[pd.Series, list[str]]:
    w = pesos[pesos > 0]
    disp = [s for s in w.index if s in precios.columns and pd.notna(precios.at[base, s])]
    faltan = [s for s in w.index if s not in disp]
    if not disp:
        return pd.Series(dtype=float), faltan
    ww = w[disp] / w[disp].sum()
    tramo = precios.loc[base:, disp].ffill()
    valor = (tramo / tramo.iloc[0] * ww.to_numpy()).sum(axis=1)
    return valor, faltan


def _metricas_curva(valor: pd.Series, rf: float, plazos: list[int]) -> dict:
    dias = len(valor) - 1
    r = valor.pct_change().dropna()
    out = {"dias": dias, "retorno_total": float(valor.iloc[-1] - 1.0) if dias >= 0 else np.nan}
    if dias >= MIN_DIAS_ANUALIZAR:
        out.update(retorno_anual=metricas.cagr(r), volatilidad=metricas.volatilidad(r),
                   sharpe=metricas.sharpe(r, rf), max_drawdown=metricas.max_drawdown(r))
    else:
        out.update(retorno_anual=np.nan, volatilidad=np.nan, sharpe=np.nan,
                   max_drawdown=metricas.max_drawdown(r) if len(r) else np.nan)
    for h in plazos:
        out[f"ret_{h}d"] = float(valor.iloc[h] - 1.0) if dias >= h else np.nan
    return out


def evaluar_corrida(corrida: dict, precios: pd.DataFrame, benchmark: str = "SPY", rf: float = 0.04,
                    plazos: list[int] | None = None) -> dict:
    """Performance de una corrida desde su fecha de datos hasta el último precio disponible."""
    plazos = plazos or corrida["metadata"].get("config", {}).get("plazos_expost", [21, 63, 126, 252])
    meta = corrida["metadata"]
    base_pedida = pd.Timestamp(meta["fecha_datos"])
    previas = precios.index[precios.index <= base_pedida]
    if len(previas) == 0:
        raise ValueError(f"No hay precios para la fecha de la corrida {meta.get('run_id')} ({base_pedida.date()})")
    base = previas[-1]
    bench = meta.get("benchmark", benchmark)
    filas, curvas, avisos = [], {}, []
    bench_val = None
    if bench in precios.columns and pd.notna(precios.at[base, bench]):
        bench_val = precios.loc[base:, bench].ffill() / precios.at[base, bench]
        curvas[f"Benchmark ({bench})"] = bench_val
    mb = _metricas_curva(bench_val, rf, plazos) if bench_val is not None else {}
    for k, w in corrida["pesos"].items():
        valor, faltan = _curva(precios, w, base)
        if faltan:
            avisos.append(f"{NOMBRES.get(k, k)}: sin precio para {', '.join(faltan)} (se reparte su peso)")
        if valor.empty:
            continue
        nombre = NOMBRES.get(k, k)
        curvas[nombre] = valor
        m = _metricas_curva(valor, rf, plazos)
        m.update(portafolio=nombre, clave=k)
        if mb:
            m["exceso_total"] = m["retorno_total"] - mb["retorno_total"]
            for h in plazos:
                m[f"exceso_{h}d"] = m[f"ret_{h}d"] - mb.get(f"ret_{h}d", np.nan)
        filas.append(m)
    if mb:
        mb.update(portafolio=f"Benchmark ({bench})", clave="benchmark", exceso_total=0.0)
        filas.append(mb)
    tabla = pd.DataFrame(filas).set_index("portafolio") if filas else pd.DataFrame()
    # Señales: retorno de cada activo desde la base
    sen = corrida["senales"].copy()
    activos = [s for s in sen.index if s in precios.columns and pd.notna(precios.at[base, s])]
    ult = precios.loc[base:, activos].ffill().iloc[-1]
    sen = sen.loc[activos].copy()
    sen["retorno_desde_corrida"] = ult / precios.loc[base, activos] - 1.0
    ret_bench = mb.get("retorno_total", np.nan) if mb else np.nan
    sen["le_gano_al_benchmark"] = sen["retorno_desde_corrida"] > ret_bench
    por_clase = (sen.groupby("clasificacion")["retorno_desde_corrida"].agg(["count", "mean", "median"])
                 .rename(columns={"count": "activos", "mean": "retorno_medio", "median": "retorno_mediano"})
                 if "clasificacion" in sen.columns else pd.DataFrame())
    ic = np.nan
    if "score" in sen.columns:
        ok = sen["score"].notna() & sen["retorno_desde_corrida"].notna()
        if ok.sum() >= 5:
            ic = float(sen.loc[ok, "score"].rank().corr(sen.loc[ok, "retorno_desde_corrida"].rank()))
    if "clasificacion" in sen.columns:
        opp = sen[sen["clasificacion"].isin(["Oportunidad", "Oportunidad con alertas"])]
    else:
        opp = sen.iloc[0:0]
    return {
        "run_id": meta.get("run_id"), "fecha_datos": base, "dias": len(precios.loc[base:]) - 1,
        "tabla": tabla, "curvas": pd.DataFrame(curvas), "senales": sen, "por_clase": por_clase,
        "ic": ic, "pct_oportunidades_ganan": float(opp["le_gano_al_benchmark"].mean()) if len(opp) else np.nan,
        "retorno_benchmark": ret_bench, "avisos": avisos,
    }


def evaluar_todas(corridas: list[dict], precios: pd.DataFrame, benchmark: str = "SPY", rf: float = 0.04,
                  plazos: list[int] | None = None) -> dict:
    """Evalúa todas las corridas y arma la tabla comparativa (ranking de estrategias)."""
    evals, tablas = [], []
    for c in corridas:
        try:
            e = evaluar_corrida(c, precios, benchmark, rf, plazos)
        except ValueError as err:
            print(f"  aviso: {err}")
            continue
        evals.append(e)
        t = e["tabla"].copy()
        t.insert(0, "run_id", e["run_id"])
        t.insert(1, "fecha_datos", e["fecha_datos"].date())
        tablas.append(t)
    todas = pd.concat(tablas) if tablas else pd.DataFrame()
    ranking = pd.DataFrame()
    if not todas.empty and "exceso_total" in todas.columns:
        sin_bench = todas[todas["clave"] != "benchmark"]
        g = sin_bench.groupby(level=0)
        ranking = pd.DataFrame({
            "corridas": g.size(),
            "retorno_medio": g["retorno_total"].mean(),
            "exceso_medio": g["exceso_total"].mean(),
            "pct_le_gana_al_benchmark": g["exceso_total"].apply(lambda x: float((x > 0).mean())),
            "dias_medios": g["dias"].mean(),
        }).sort_values("exceso_medio", ascending=False)
    senales = pd.DataFrame([{"run_id": e["run_id"], "fecha_datos": e["fecha_datos"].date(), "dias": e["dias"],
                             "ic_score_vs_retorno": e["ic"], "pct_oportunidades_ganan": e["pct_oportunidades_ganan"],
                             "retorno_benchmark": e["retorno_benchmark"]} for e in evals])
    return {"evaluaciones": evals, "todas": todas, "ranking": ranking, "senales": senales}
