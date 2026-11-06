"""Qué comprar: pasa los pesos de un portafolio a cantidades con un capital en USD.

- Broker de EE.UU.: acciones/ETFs originales al último precio.
- CEDEARs (BYMA): especie D (dólar MEP) de data912; si solo cotiza en pesos, se pasa a dólares con el MEP
  implícito. Los activos sin CEDEAR se marcan para comprar en EE.UU. (decisión del usuario 2026-11-06:
  calcular las dos opciones).

Sin fracciones se usa el método greedy: primero la parte entera de cada posición y después, con lo que
sobra, se compra de a una unidad la posición más lejos de su objetivo (si comprarla acerca al objetivo y
alcanza la plata). Nunca se gasta más que el capital.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def asignacion_discreta(pesos: pd.Series, precios: pd.Series, capital: float, fracciones: bool = False,
                        decimales: int = 4, fraccionables: set | None = None) -> tuple[pd.DataFrame, float]:
    """Cantidades a comprar. Devuelve (tabla, efectivo sobrante). Los activos sin precio quedan con
    cantidad 0 y una nota. ``fraccionables``: activos que se compran en fracciones aunque
    ``fracciones=False`` (cripto: 1 BTC vale decenas de miles de dólares)."""
    w = pd.Series(pesos, dtype=float)
    w = w[w > 0]
    p = pd.Series(precios, dtype=float).reindex(w.index)
    sin_precio = p.isna() | (p <= 0)
    cant = pd.Series(0.0, index=w.index)
    ok = ~sin_precio
    objetivo = w * capital
    factor = 10 ** decimales
    frac = pd.Series(bool(fracciones), index=w.index)
    if fraccionables:
        frac[frac.index.isin(list(fraccionables))] = True
    f_ok, e_ok = ok & frac, ok & ~frac
    cant[f_ok] = np.floor(objetivo[f_ok] / p[f_ok] * factor) / factor
    cant[e_ok] = np.floor(objetivo[e_ok] / p[e_ok])
    restante = capital - float((cant[ok] * p[ok]).sum())
    if e_ok.any():
        for _ in range(100_000):
            deficit = (objetivo - cant * p)[e_ok]
            pe = p[e_ok]
            utiles = deficit[(pe <= restante + 1e-9) & (deficit > pe / 2.0)]
            if utiles.empty:
                break
            s = utiles.idxmax()
            cant[s] += 1
            restante -= float(p[s])
    monto = (cant * p).where(ok, 0.0)
    invertido = float(monto.sum())
    tabla = pd.DataFrame({
        "peso_objetivo": w,
        "precio": p,
        "cantidad": cant,
        "monto": monto,
        "peso_real": monto / invertido if invertido > 0 else 0.0,
    })
    tabla["nota"] = np.where(sin_precio, "sin precio", np.where((cant == 0) & ok, "no alcanza para 1 unidad", ""))
    tabla.index.name = "activo"
    return tabla.sort_values("peso_objetivo", ascending=False), max(restante, 0.0)


def precios_cedears(mapa_cedear: dict[str, str], cotizaciones: pd.DataFrame | None,
                    mep: float | None) -> pd.DataFrame:
    """Precio en USD de un CEDEAR por activo: especie D si cotiza; si no, precio en pesos / MEP implícito.
    Devuelve una tabla indexada por símbolo de Yahoo con: especie, precio_usd, fuente, volumen."""
    filas = {}
    if cotizaciones is None or cotizaciones.empty:
        return pd.DataFrame(columns=["especie", "precio_usd", "fuente", "volumen"])
    for activo, base in mapa_cedear.items():
        if not base:
            continue
        esp_d = f"{base}D"
        if esp_d in cotizaciones.index and cotizaciones.at[esp_d, "c"] > 0:
            filas[activo] = {"especie": esp_d, "precio_usd": float(cotizaciones.at[esp_d, "c"]),
                             "fuente": "especie D (dólar MEP)",
                             "volumen": cotizaciones.at[esp_d, "v"] if "v" in cotizaciones.columns else np.nan}
        elif base in cotizaciones.index and mep and cotizaciones.at[base, "c"] > 0:
            filas[activo] = {"especie": base, "precio_usd": float(cotizaciones.at[base, "c"]) / mep,
                             "fuente": f"pesos / MEP implícito ({mep:,.0f})",
                             "volumen": cotizaciones.at[base, "v"] if "v" in cotizaciones.columns else np.nan}
    df = pd.DataFrame.from_dict(filas, orient="index")
    df.index.name = "activo"
    return df


def con_equivalentes(tabla_cedears: pd.DataFrame, gemelos: list[list[str]]) -> pd.DataFrame:
    """Si el representante de un grupo de gemelos no tiene CEDEAR pero un equivalente sí (BTC-USD -> IBIT),
    usa el CEDEAR del equivalente para el representante."""
    t = tabla_cedears.copy()
    for g in gemelos:
        rep = g[0]
        if rep in t.index:
            continue
        for eq in g[1:]:
            if eq in t.index:
                fila = t.loc[eq].copy()
                fila["fuente"] = f"{fila['fuente']}; equivalente de {rep}: {eq}"
                t.loc[rep] = fila
                break
    return t


def asignacion_con_cedears(pesos: pd.Series, precios_usd: pd.Series, tabla_cedears: pd.DataFrame,
                           capital: float, fracciones: bool = False, fraccionables: set | None = None
                           ) -> tuple[pd.DataFrame, float]:
    """Asignación mixta: CEDEARs para los activos que tienen, acciones/ETFs de EE.UU. para el resto.
    Devuelve (tabla con columna ``vehiculo``, efectivo sobrante)."""
    w = pd.Series(pesos, dtype=float)
    w = w[w > 0]
    con = [s for s in w.index if s in tabla_cedears.index]
    sin = [s for s in w.index if s not in con]
    partes, sobrante = [], 0.0
    if con:
        cap = capital * float(w[con].sum())
        t, r = asignacion_discreta(w[con] / w[con].sum(), tabla_cedears.loc[con, "precio_usd"], cap, fracciones)
        t["peso_objetivo"] = w[con]
        t["vehiculo"] = ["CEDEAR " + tabla_cedears.at[s, "especie"] for s in t.index]
        t["fuente_precio"] = [tabla_cedears.at[s, "fuente"] for s in t.index]
        partes.append(t)
        sobrante += r
    if sin:
        cap = capital * float(w[sin].sum())
        t, r = asignacion_discreta(w[sin] / w[sin].sum(), precios_usd.reindex(sin), cap, fracciones,
                                   fraccionables=fraccionables)
        t["peso_objetivo"] = w[sin]
        t["vehiculo"] = "sin CEDEAR: comprar en EE.UU."
        t["fuente_precio"] = "último cierre (Yahoo)"
        partes.append(t)
        sobrante += r
    tabla = pd.concat(partes) if partes else pd.DataFrame()
    if not tabla.empty:
        inv = float(tabla["monto"].sum())
        tabla["peso_real"] = tabla["monto"] / inv if inv > 0 else 0.0
        tabla = tabla.sort_values("peso_objetivo", ascending=False)
    return tabla, sobrante
