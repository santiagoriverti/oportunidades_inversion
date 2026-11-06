"""Score de oportunidad: ¿qué activos están artificialmente bajos?

Método (docs/METODOLOGIA.md §3):
1. Cada métrica se orienta para que "más alto = más oportunidad" y se convierte en percentil dentro del
   universo (0 = el menos barato, 1 = el más barato). Los percentiles no dependen de la escala ni de valores
   extremos.
2. Promedio de percentiles por grupo: técnico, estadístico y fundamental (solo acciones con datos).
3. Score = promedio ponderado de los grupos disponibles (pesos según el horizonte), de 0 a 100.
4. El score es RELATIVO al universo; por eso también se cuentan las señales ABSOLUTAS que se cumplen (precio
   debajo de su media de 200 días, RSI < 30, etc.). "Oportunidad" = score alto Y al menos 2 señales.
5. Alertas: caída fuerte en tendencia bajista (cuchillo que cae), ganancias esperadas en baja (posible
   trampa de valor), precio por encima del objetivo de los analistas, poca historia.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# métrica: (grupo, orientación). Orientación -1 = cuanto más baja la métrica, más "barato".
METRICAS: dict[str, tuple[str, int]] = {
    "dist_sma50": ("tecnico", -1),
    "dist_sma200": ("tecnico", -1),
    "posicion_52s": ("tecnico", -1),
    "rsi_14": ("tecnico", -1),
    "bollinger_pctb": ("tecnico", -1),
    "zscore_1a": ("estadistico", -1),
    "z_tendencia_3a": ("estadistico", -1),
    "z_ret_3m": ("estadistico", -1),
    "z_relativo_bench": ("estadistico", -1),
    "upside_analistas": ("fundamental", +1),
    "pe_relativo_sector": ("fundamental", -1),
    "peg": ("fundamental", -1),
    "fcf_yield": ("fundamental", +1),
}
GRUPOS = ("tecnico", "estadistico", "fundamental")
# mínimo de métricas disponibles para que un grupo cuente
MINIMO_POR_GRUPO = {"tecnico": 3, "estadistico": 2, "fundamental": 2}

CLASES = ["Oportunidad", "Oportunidad con alertas", "Vigilar", "Neutral", "Sobreextendida",
          "Sin datos suficientes"]


def percentil(serie: pd.Series, orientacion: int) -> pd.Series:
    """Percentil centrado en (0, 1): (rango - 0,5) / n, con la orientación aplicada. NaN se mantiene."""
    s = pd.to_numeric(serie, errors="coerce") * orientacion
    n = s.notna().sum()
    if n == 0:
        return s * np.nan
    return (s.rank(method="average") - 0.5) / n


def _reglas(u: dict) -> list[tuple[str, callable, str]]:
    return [
        ("dist_sma200", lambda v: v < u["dist_sma200"], "debajo de su media de 200 días"),
        ("zscore_1a", lambda v: v <= u["zscore_1a"], f"z-score de 1 año ≤ {u['zscore_1a']:g}"),
        ("z_tendencia_3a", lambda v: v <= u["z_tendencia_3a"], f"debajo de su tendencia de 3 años ({u['z_tendencia_3a']:g} desvíos)"),
        ("rsi_14", lambda v: v <= u["rsi_14"], f"RSI ≤ {u['rsi_14']:g} (sobrevendido)"),
        ("bollinger_pctb", lambda v: v <= u["bollinger_pctb"], "debajo de la banda inferior de Bollinger"),
        ("drawdown_52s", lambda v: v <= u["drawdown_52s"], f"cayó {abs(u['drawdown_52s']):.0%} o más desde el máximo de 52 semanas"),
        ("z_ret_3m", lambda v: v <= u["z_ret_3m"], f"caída de 3 meses inusual ({u['z_ret_3m']:g} desvíos)"),
        ("z_relativo_bench", lambda v: v <= u["z_relativo_bench"], "muy por debajo de lo normal contra el benchmark"),
        ("upside_analistas", lambda v: v >= u["upside_analistas"], f"upside de analistas ≥ {u['upside_analistas']:.0%}"),
        ("pe_relativo_sector", lambda v: v <= u["pe_relativo_sector"], f"P/E {1 - u['pe_relativo_sector']:.0%}+ debajo de su sector"),
        ("peg", lambda v: 0 < v < u["peg"], f"PEG < {u['peg']:g}"),
    ]


def senales_activas(fila: pd.Series, umbrales: dict) -> list[str]:
    """Lista de señales absolutas que cumple un activo."""
    out = []
    for col, regla, texto in _reglas(umbrales):
        v = fila.get(col, np.nan)
        if v is not None and pd.notna(v) and regla(float(v)):
            out.append(texto)
    return out


def alertas(fila: pd.Series) -> list[str]:
    out = []
    r1m, d50, tend = fila.get("ret_1m", np.nan), fila.get("dist_sma50", np.nan), fila.get("tendencia_alcista", np.nan)
    if pd.notna(r1m) and r1m <= -0.15 and pd.notna(d50) and d50 < 0 and tend == 0:
        out.append("cuchillo que cae: -15% en un mes y tendencia bajista")
    ci = fila.get("crec_implicito", np.nan)
    if pd.notna(ci) and ci <= -0.10:
        out.append("posible trampa de valor: el mercado espera menores ganancias")
    up = fila.get("upside_analistas", np.nan)
    if pd.notna(up) and up < 0:
        out.append("precio por encima del objetivo de los analistas")
    dias = fila.get("dias_historia", np.nan)
    if pd.notna(dias) and dias < 252:
        out.append(f"poca historia ({int(dias)} días)")
    return out


ALERTAS_GRAVES = ("cuchillo", "trampa", "objetivo de los analistas")


def calcular_score(foto: pd.DataFrame, fundamentales: pd.DataFrame | None, pesos_grupos: dict,
                   umbrales: dict, umbral_oportunidad: float = 70.0, min_senales: int = 2) -> pd.DataFrame:
    """Score de oportunidad (0-100), señales, alertas y clasificación de cada activo de ``foto``.

    ``foto``: indicadores a una fecha (indicadores.foto + reversion_media opcional).
    ``fundamentales``: tabla de fundamentales.tabla_fundamentales (None en el backtest).
    """
    df = foto.copy()
    if fundamentales is not None and not fundamentales.empty:
        cols = [c for c in fundamentales.columns if c not in df.columns]
        df = df.join(fundamentales[cols], how="left")
    for m in METRICAS:
        if m not in df.columns:
            df[m] = np.nan
    pct = pd.DataFrame({m: percentil(df[m], o) for m, (_, o) in METRICAS.items()}, index=df.index)
    for g in GRUPOS:
        cols = [m for m, (gr, _) in METRICAS.items() if gr == g]
        disponibles = pct[cols].notna().sum(axis=1)
        df[f"score_{g}"] = (pct[cols].mean(axis=1) * 100).where(disponibles >= MINIMO_POR_GRUPO[g])
    pesos = pd.Series({g: max(float(pesos_grupos.get(g, 0.0)), 0.0) for g in GRUPOS})
    S = df[[f"score_{g}" for g in GRUPOS]]
    S.columns = list(GRUPOS)
    w = S.notna().astype(float).mul(pesos, axis=1)
    hay_precio = S[["tecnico", "estadistico"]].notna().any(axis=1)
    df["score"] = ((S.fillna(0) * w).sum(axis=1) / w.sum(axis=1).where(w.sum(axis=1) > 0)).where(hay_precio)
    df["senales"] = [senales_activas(f, umbrales) for _, f in df.iterrows()]
    df["n_senales"] = df["senales"].map(len)
    df["alertas"] = [alertas(f) for _, f in df.iterrows()]

    def clasificar(f) -> str:
        sc, n = f["score"], f["n_senales"]
        if pd.isna(sc):
            return "Sin datos suficientes"
        graves = any(any(k in a for k in ALERTAS_GRAVES) for a in f["alertas"])
        if sc >= umbral_oportunidad and n >= min_senales:
            return "Oportunidad con alertas" if graves else "Oportunidad"
        if sc >= umbral_oportunidad - 10 or n >= min_senales:
            return "Vigilar"
        if sc <= 30:
            return "Sobreextendida"
        return "Neutral"

    df["clasificacion"] = df.apply(clasificar, axis=1)
    df["senales"] = df["senales"].map("; ".join)
    df["alertas"] = df["alertas"].map("; ".join)
    df = df.sort_values(["score", "n_senales"], ascending=[False, False], na_position="last")
    df["ranking"] = np.arange(1, len(df) + 1)
    df.loc[df["score"].isna(), "ranking"] = np.nan
    return df


def top_oportunidades(tabla: pd.DataFrame, n: int, incluir_alertas: bool = True) -> list[str]:
    """Los n activos con mejor score entre los clasificados como oportunidad (o, si no alcanzan, los de mejor
    score en general con al menos 1 señal)."""
    clases = ["Oportunidad", "Oportunidad con alertas"] if incluir_alertas else ["Oportunidad"]
    elegidos = tabla[tabla["clasificacion"].isin(clases)].index.tolist()
    if len(elegidos) < n:
        resto = tabla[(~tabla.index.isin(elegidos)) & tabla["score"].notna() & (tabla["n_senales"] >= 1)]
        elegidos += resto.index.tolist()[: n - len(elegidos)]
    return elegidos[:n]
