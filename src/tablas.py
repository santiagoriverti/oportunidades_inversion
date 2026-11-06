"""Tablas con formato (pandas Styler) para mostrar en los notebooks. Cada gráfico tiene su tabla."""
from __future__ import annotations

import pandas as pd

GUION = "–"

COLUMNAS_SENALES = {
    "nombre": "nombre", "clasificacion": "clasificación", "score": "score", "n_senales": "señales",
    "precio": "precio USD", "ret_1m": "1 mes", "ret_3m": "3 meses", "ret_12m": "12 meses",
    "dist_sma200": "vs media 200d", "zscore_1a": "z 1 año", "z_tendencia_3a": "z tendencia 3a",
    "rsi_14": "RSI", "drawdown_52s": "caída 52 sem.", "upside_analistas": "upside analistas",
    "pe_forward": "P/E forward", "pe_relativo_sector": "P/E vs sector", "media_vida_dias": "media vida (días)",
    "senales": "señales activas", "alertas": "alertas",
}
FORMATO_SENALES = {
    "score": "{:.0f}", "señales": "{:.0f}", "precio USD": "{:,.2f}", "1 mes": "{:+.1%}", "3 meses": "{:+.1%}",
    "12 meses": "{:+.1%}", "vs media 200d": "{:+.1%}", "z 1 año": "{:+.2f}", "z tendencia 3a": "{:+.2f}",
    "RSI": "{:.0f}", "caída 52 sem.": "{:.1%}", "upside analistas": "{:+.1%}", "P/E forward": "{:.1f}",
    "P/E vs sector": "{:.2f}", "media vida (días)": "{:.0f}",
}


def tabla_senales(tabla: pd.DataFrame, n: int | None = 30, solo: list[str] | None = None) -> pd.DataFrame:
    """Subconjunto legible de la tabla de señales (columnas renombradas en castellano)."""
    t = tabla if solo is None else tabla[tabla["clasificacion"].isin(solo)]
    t = t.head(n) if n else t
    cols = [c for c in COLUMNAS_SENALES if c in t.columns]
    return t[cols].rename(columns=COLUMNAS_SENALES)


def estilo_senales(tabla: pd.DataFrame, n: int | None = 30, solo: list[str] | None = None):
    t = tabla_senales(tabla, n, solo)
    fmt = {k: v for k, v in FORMATO_SENALES.items() if k in t.columns}
    st = t.style.format(fmt, na_rep=GUION)
    if "score" in t.columns and t["score"].notna().any():
        st = st.background_gradient(cmap="Blues", subset=["score"], vmin=0, vmax=100)
    return st.set_properties(subset=[c for c in ("señales activas", "alertas") if c in t.columns],
                             **{"white-space": "normal", "min-width": "220px", "font-size": "0.85em"})


def estilo_porcentajes(df: pd.DataFrame, pct: list[str] | None = None, dec: dict | None = None, gradiente: str | None = None):
    """Formato genérico: columnas en porcentaje, decimales por columna y gradiente opcional."""
    pct = [c for c in (pct or []) if c in df.columns]
    fmt = {c: "{:.1%}" for c in pct}
    for c, f in (dec or {}).items():
        if c in df.columns:
            fmt[c] = f
    st = df.style.format(fmt, na_rep=GUION)
    if gradiente and gradiente in df.columns and df[gradiente].notna().any():
        st = st.background_gradient(cmap="Blues", subset=[gradiente])
    return st


def estilo_metricas(df: pd.DataFrame):
    return estilo_porcentajes(
        df, pct=["retorno_anual", "volatilidad", "max_drawdown", "var_95", "cvar_95", "alfa", "retorno_total"],
        dec={"sharpe": "{:.2f}", "sortino": "{:.2f}", "calmar": "{:.2f}", "beta": "{:.2f}",
             "correlacion_bench": "{:.2f}", "asimetria": "{:.2f}", "curtosis": "{:.1f}", "dias": "{:.0f}"},
        gradiente="sharpe")


def estilo_resumen_portafolios(df: pd.DataFrame):
    return estilo_porcentajes(
        df, pct=["retorno_esperado", "volatilidad", "peso_maximo", "retorno_hist", "volatilidad_hist",
                 "max_drawdown_hist"],
        dec={"sharpe": "{:.2f}", "n_efectivo": "{:.1f}", "sharpe_hist": "{:.2f}", "n_activos": "{:.0f}"},
        gradiente="sharpe")


def estilo_asignacion(df: pd.DataFrame):
    return estilo_porcentajes(df, pct=["peso_objetivo", "peso_real"],
                              dec={"precio": "{:,.2f}", "cantidad": "{:,.4g}", "monto": "{:,.2f}"})


def estilo_backtest(df: pd.DataFrame):
    return estilo_porcentajes(
        df, pct=["retorno_anual", "volatilidad", "max_drawdown", "var_95", "cvar_95", "retorno_total",
                 "rotacion_media", "exceso_vs_benchmark"],
        dec={"sharpe": "{:.2f}", "sortino": "{:.2f}", "calmar": "{:.2f}", "asimetria": "{:.2f}",
             "curtosis": "{:.1f}", "periodos": "{:.0f}"},
        gradiente="sharpe")


def estilo_expost(df: pd.DataFrame):
    pct = [c for c in df.columns if c.startswith(("ret_", "exceso_", "retorno_"))] + ["volatilidad", "max_drawdown"]
    return estilo_porcentajes(df, pct=pct, dec={"sharpe": "{:.2f}", "dias": "{:.0f}", "corridas": "{:.0f}",
                                                "dias_medios": "{:.0f}"})
