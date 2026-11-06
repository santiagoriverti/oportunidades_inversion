"""Gráficos interactivos (plotly) del análisis, el backtest y el seguimiento ex-post.

Paleta de referencia validada (skill dataviz, `validate_palette.js --mode light`: pasa CVD y visión normal;
aqua, amarillo y magenta tienen contraste < 3:1 con el fondo, por eso cada gráfico tiene su tabla y los
portafolios llevan además símbolo y etiqueta). Reglas: un color fijo por portafolio en TODOS los gráficos
(nunca por ranking), secuencial de un solo tono (azul) para magnitudes, divergente azul <-> rojo con gris en
el medio para correlaciones y excesos, grilla y ejes en líneas finas, sin doble eje.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import indicadores
from .portafolios import NOMBRES, contribuciones_riesgo
from .senales import METRICAS, percentil

SUPERFICIE = "#fcfcfb"
GRILLA = "#e1e0d9"
EJE = "#c3c2b7"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
TENUE = "#898781"
FUENTE = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

CATEGORICA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SECUENCIAL = [[0.0, "#cde2fb"], [0.2, "#9ec5f4"], [0.4, "#6da7ec"], [0.6, "#3987e5"], [0.8, "#1c5cab"],
              [1.0, "#0d366b"]]
DIVERGENTE = [[0.0, "#184f95"], [0.2, "#5598e7"], [0.4, "#cde2fb"], [0.5, "#f0efec"], [0.6, "#f6c9c8"],
              [0.8, "#e34948"], [1.0, "#a8302f"]]
AZUL, ROJO = "#2a78d6", "#e34948"

COLOR_PORTAFOLIO = {k: CATEGORICA[i] for i, k in enumerate(NOMBRES)}
SIMBOLO_PORTAFOLIO = dict(zip(NOMBRES, ["circle", "square", "diamond", "triangle-up", "triangle-down",
                                        "cross", "x", "star"]))
COLOR_BENCHMARK = TINTA_2
COLOR_CLASE = {
    "Oportunidad": "#2a78d6",
    "Oportunidad con alertas": "#eb6834",
    "Vigilar": "#9ec5f4",
    "Neutral": "#c3c2b7",
    "Sobreextendida": "#a8a7a0",
    "Sin datos suficientes": "#e1e0d9",
}
ETIQUETA_METRICA = {
    "dist_sma50": "vs media 50d", "dist_sma200": "vs media 200d", "posicion_52s": "rango 52 sem.",
    "rsi_14": "RSI 14", "bollinger_pctb": "Bollinger %B", "zscore_1a": "z-score 1 año",
    "z_tendencia_3a": "vs tendencia 3 años", "z_ret_3m": "caída 3m (z)", "z_relativo_bench": "vs benchmark (z)",
    "upside_analistas": "upside analistas", "pe_relativo_sector": "P/E vs sector", "peg": "PEG",
    "fcf_yield": "FCF yield",
}


def _color(clave: str) -> str:
    return COLOR_PORTAFOLIO.get(clave, COLOR_BENCHMARK)


def _clave_por_nombre(nombre: str) -> str:
    for k, v in NOMBRES.items():
        if v == nombre:
            return k
    return nombre


def _estilo(fig: go.Figure, titulo: str, alto: int = 480, leyenda: bool = True) -> go.Figure:
    fig.update_layout(
        title={"text": titulo, "x": 0.0, "xanchor": "left", "font": {"size": 16, "color": TINTA}},
        font={"family": FUENTE, "size": 12, "color": TINTA_2},
        paper_bgcolor=SUPERFICIE, plot_bgcolor=SUPERFICIE, height=alto,
        margin={"l": 70, "r": 30, "t": 70, "b": 50},
        showlegend=leyenda,
        legend={"bgcolor": "rgba(0,0,0,0)", "font": {"color": TINTA_2}},
        hoverlabel={"bgcolor": "white", "font": {"family": FUENTE, "color": TINTA}},
    )
    fig.update_xaxes(gridcolor=GRILLA, linecolor=EJE, zerolinecolor=EJE, tickfont={"color": TENUE},
                     showline=True, linewidth=1)
    fig.update_yaxes(gridcolor=GRILLA, linecolor=EJE, zerolinecolor=EJE, tickfont={"color": TENUE},
                     showline=True, linewidth=1)
    try:  # extremos redondeados en barras (plotly >= 5.19)
        fig.update_layout(barcornerradius=4)
    except (ValueError, TypeError):
        pass
    return fig


# ----------------------------------------------------------------------------------------------- señales
def fig_ranking(tabla: pd.DataFrame, n: int = 30, nombres: dict | None = None) -> go.Figure:
    """Barras horizontales del score de oportunidad (los n mejores), color por clasificación."""
    t = tabla[tabla["score"].notna()].head(n).iloc[::-1]
    nombres = nombres or {}
    fig = go.Figure()
    for clase, color in COLOR_CLASE.items():
        s = t[t["clasificacion"] == clase]
        if s.empty:
            continue
        texto = [f"{v:.0f}" if clase.startswith("Oportunidad") else "" for v in s["score"]]
        fig.add_bar(
            y=s.index, x=s["score"], orientation="h", name=clase, marker_color=color,
            text=texto, textposition="outside", textfont={"color": TINTA_2},
            customdata=np.stack([[nombres.get(i, "") for i in s.index], s["n_senales"],
                                 s["senales"].replace("", "-"), s["alertas"].replace("", "-")], axis=1),
            hovertemplate="<b>%{y}</b> %{customdata[0]}<br>score %{x:.1f} · %{customdata[1]} señales"
                          "<br>señales: %{customdata[2]}<br>alertas: %{customdata[3]}<extra></extra>",
        )
    fig.update_layout(barmode="overlay", bargap=0.25, xaxis_range=[0, 105], xaxis_title="score (0-100)",
                      yaxis={"categoryorder": "array", "categoryarray": list(t.index)},
                      legend={"orientation": "h", "y": 1.02, "yanchor": "bottom", "x": 0})
    return _estilo(fig, f"Score de oportunidad — {len(t)} mejores", alto=max(380, 22 * len(t) + 140))


def fig_mapa_senales(tabla: pd.DataFrame, n: int = 25) -> go.Figure:
    """Percentil de cada métrica (100 = la más 'barata' del universo) para los n mejores activos."""
    t = tabla[tabla["score"].notna()].head(n)
    metr = [m for m in METRICAS if m in tabla.columns and tabla[m].notna().any()]
    z = pd.DataFrame({m: percentil(tabla[m], o).reindex(t.index) * 100 for m, (_, o) in METRICAS.items()
                      if m in metr})
    crudo = t[metr]
    fig = go.Figure(go.Heatmap(
        z=z.to_numpy(), x=[ETIQUETA_METRICA.get(m, m) for m in metr], y=list(t.index),
        customdata=crudo.to_numpy(), colorscale=SECUENCIAL, zmin=0, zmax=100, xgap=2, ygap=2,
        colorbar={"title": "percentil", "thickness": 12},
        hovertemplate="<b>%{y}</b> · %{x}<br>percentil %{z:.0f}<br>valor %{customdata:.3f}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(side="top", showgrid=False, tickangle=-30)
    fig = _estilo(fig, "Por qué: percentil de cada métrica (más oscuro = más barato vs el universo)",
                  alto=max(420, 22 * len(t) + 180), leyenda=False)
    fig.update_layout(margin={"t": 140})
    return fig


def fig_precios(precios: pd.DataFrame, activos: list[str], dias: int = 504) -> go.Figure:
    """Precio con medias de 50 y 200 días y bandas de Bollinger; menú para elegir el activo."""
    activos = [a for a in activos if a in precios.columns]
    fig = go.Figure()
    por_activo = 5
    for i, a in enumerate(activos):
        p = precios[a].dropna()
        s50, s200 = indicadores.sma(p, 50), indicadores.sma(p, 200)
        m20, d20 = p.rolling(20).mean(), p.rolling(20).std()
        p, s50, s200, sup, inf = (x.iloc[-dias:] for x in (p, s50, s200, m20 + 2 * d20, m20 - 2 * d20))
        vis = i == 0
        fig.add_scatter(x=sup.index, y=sup, line={"width": 0}, hoverinfo="skip", showlegend=False, visible=vis)
        fig.add_scatter(x=inf.index, y=inf, line={"width": 0}, fill="tonexty", fillcolor="rgba(42,120,214,0.10)",
                        name="Bollinger (20d, ±2σ)", hoverinfo="skip", visible=vis)
        fig.add_scatter(x=s200.index, y=s200, name="media 200 días", line={"color": CATEGORICA[2], "width": 2},
                        visible=vis, hovertemplate="media 200d %{y:,.2f}<extra></extra>")
        fig.add_scatter(x=s50.index, y=s50, name="media 50 días", line={"color": CATEGORICA[1], "width": 2},
                        visible=vis, hovertemplate="media 50d %{y:,.2f}<extra></extra>")
        fig.add_scatter(x=p.index, y=p, name=f"precio {a}", line={"color": CATEGORICA[0], "width": 2},
                        visible=vis, hovertemplate="precio %{y:,.2f}<extra></extra>")
    botones = []
    for i, a in enumerate(activos):
        vis = [False] * (por_activo * len(activos))
        vis[por_activo * i: por_activo * (i + 1)] = [True] * por_activo
        botones.append({"label": a, "method": "update", "args": [{"visible": vis},
                                                                  {"title.text": f"{a}: precio, medias y Bollinger (USD)"}]})
    fig.update_layout(hovermode="x unified", yaxis_title="USD",
                      updatemenus=[{"buttons": botones, "direction": "down", "x": 1.0, "xanchor": "right", "y": 1.13,
                                    "yanchor": "top", "bgcolor": "white", "bordercolor": EJE}] if len(activos) > 1 else [],
                      legend={"orientation": "h", "y": -0.15, "x": 0})
    return _estilo(fig, f"{activos[0] if activos else ''}: precio, medias y Bollinger (USD)", alto=500)


# ----------------------------------------------------------------------------------------------- portafolios
def fig_frontera(frontera: pd.DataFrame | None, mu: pd.Series, cov: pd.DataFrame, pesos: dict[str, pd.Series],
                 rf: float) -> go.Figure:
    """Frontera eficiente, activos individuales y los portafolios (color + símbolo + etiqueta)."""
    vol = np.sqrt(np.diag(cov.to_numpy()))
    fig = go.Figure()
    fig.add_scatter(x=vol * 100, y=mu.reindex(cov.index) * 100, mode="markers", name="activos",
                    marker={"size": 7, "color": EJE, "line": {"color": SUPERFICIE, "width": 1}},
                    text=list(cov.index), hovertemplate="<b>%{text}</b><br>vol %{x:.1f}% · ret %{y:.1f}%<extra></extra>")
    if frontera is not None and not frontera.empty:
        fig.add_scatter(x=frontera["volatilidad"] * 100, y=frontera["retorno"] * 100, mode="lines",
                        name="frontera eficiente", line={"color": TINTA_2, "width": 2},
                        hovertemplate="vol %{x:.1f}% · ret %{y:.1f}%<extra>frontera</extra>")
    S = cov.to_numpy()
    for k, w in pesos.items():
        if w is None:
            continue
        ww = w.reindex(cov.index).fillna(0.0).to_numpy()
        v, r = float(np.sqrt(ww @ S @ ww)) * 100, float(ww @ mu.reindex(cov.index).fillna(0).to_numpy()) * 100
        fig.add_scatter(x=[v], y=[r], mode="markers+text", name=NOMBRES.get(k, k), text=[NOMBRES.get(k, k)],
                        textposition="middle right", textfont={"color": TINTA_2, "size": 11},
                        marker={"size": 13, "color": _color(k), "symbol": SIMBOLO_PORTAFOLIO.get(k, "circle"),
                                "line": {"color": SUPERFICIE, "width": 2}},
                        hovertemplate=f"<b>{NOMBRES.get(k, k)}</b><br>vol %{{x:.1f}}% · ret %{{y:.1f}}%"
                                      f"<br>Sharpe {(r / 100 - rf) / (v / 100) if v > 0 else float('nan'):.2f}<extra></extra>")
    fig.update_layout(xaxis_title="volatilidad anual esperada (%)", yaxis_title="retorno anual esperado (%)",
                      legend={"orientation": "v", "x": 1.02, "y": 1})
    return _estilo(fig, "Frontera eficiente y portafolios (retornos esperados del modelo)", alto=560)


def fig_pesos(pesos: dict[str, pd.Series], max_filas: int = 30) -> go.Figure:
    """Mapa de calor activo x portafolio con los pesos (los activos más pesados; el resto en 'otros')."""
    df = pd.DataFrame({NOMBRES.get(k, k): w for k, w in pesos.items() if w is not None}).fillna(0.0)
    if df.empty:
        return _estilo(go.Figure(), "Pesos por portafolio (sin datos)")
    orden = df.max(axis=1).sort_values(ascending=False).index
    arriba, resto = list(orden[:max_filas]), list(orden[max_filas:])
    tabla = df.loc[arriba]
    if resto:
        tabla.loc[f"otros ({len(resto)})"] = df.loc[resto].sum()
    texto = np.where(tabla.to_numpy() >= 0.05, (tabla * 100).round(0).astype(int).astype(str) + "%", "")
    fig = go.Figure(go.Heatmap(
        z=tabla.to_numpy() * 100, x=list(tabla.columns), y=list(tabla.index), colorscale=SECUENCIAL,
        zmin=0, zmax=max(5.0, float(tabla.to_numpy().max() * 100)), xgap=2, ygap=2, text=texto,
        texttemplate="%{text}", textfont={"size": 10}, colorbar={"title": "peso %", "thickness": 12},
        hovertemplate="<b>%{y}</b> en %{x}: %{z:.1f}%<extra></extra>"))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(side="top", showgrid=False, tickangle=-25)
    fig = _estilo(fig, "Pesos de cada portafolio (%)", alto=max(420, 20 * len(tabla) + 200), leyenda=False)
    fig.update_layout(margin={"t": 150})
    return fig


def fig_contribucion_riesgo(pesos: dict[str, pd.Series], cov: pd.DataFrame, top: int = 15) -> go.Figure:
    """Peso vs aporte al riesgo de cada activo (menú por portafolio): quién manda en el riesgo."""
    claves = [k for k, w in pesos.items() if w is not None]
    fig = go.Figure()
    for i, k in enumerate(claves):
        w = pesos[k].reindex(cov.index).fillna(0.0)
        rc = contribuciones_riesgo(w, cov)
        sel = w.sort_values(ascending=False).head(top).index[::-1]
        vis = i == 0
        fig.add_bar(y=list(sel), x=w[sel] * 100, orientation="h", name="peso", marker_color=CATEGORICA[0],
                    visible=vis, hovertemplate="%{y}: peso %{x:.1f}%<extra></extra>")
        fig.add_bar(y=list(sel), x=rc[sel] * 100, orientation="h", name="aporte al riesgo",
                    marker_color=CATEGORICA[1], visible=vis, hovertemplate="%{y}: aporte al riesgo %{x:.1f}%<extra></extra>")
    botones = []
    for i, k in enumerate(claves):
        vis = [False] * (2 * len(claves))
        vis[2 * i: 2 * i + 2] = [True, True]
        botones.append({"label": NOMBRES.get(k, k), "method": "update",
                        "args": [{"visible": vis}, {"title.text": f"Peso vs aporte al riesgo — {NOMBRES.get(k, k)}"}]})
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.1, xaxis_title="%",
                      updatemenus=[{"buttons": botones, "direction": "down", "x": 1.0, "xanchor": "right", "y": 1.14,
                                    "yanchor": "top", "bgcolor": "white", "bordercolor": EJE}],
                      legend={"orientation": "h", "y": -0.12, "x": 0})
    titulo = f"Peso vs aporte al riesgo — {NOMBRES.get(claves[0], claves[0])}" if claves else "Aporte al riesgo"
    return _estilo(fig, titulo, alto=max(420, 28 * top + 160))


def fig_correlaciones(cov: pd.DataFrame, orden: list[str] | None = None) -> go.Figure:
    """Correlaciones (ordenadas por agrupamiento jerárquico): azul = se mueven al revés, rojo = juntos."""
    sd = np.sqrt(np.diag(cov.to_numpy()))
    corr = pd.DataFrame(cov.to_numpy() / np.outer(sd, sd), index=cov.index, columns=cov.columns)
    if orden:
        corr = corr.loc[orden, orden]
    n = len(corr)
    fig = go.Figure(go.Heatmap(z=corr.to_numpy(), x=list(corr.columns), y=list(corr.index), colorscale=DIVERGENTE,
                               zmin=-1, zmax=1, colorbar={"title": "correlación", "thickness": 12},
                               hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>"))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont={"size": 9 if n > 40 else 11})
    fig.update_xaxes(showgrid=False, tickfont={"size": 9 if n > 40 else 11}, tickangle=-90)
    return _estilo(fig, "Correlaciones de los retornos (ventana de optimización)", alto=min(1100, max(500, 14 * n + 180)),
                   leyenda=False)


# ----------------------------------------------------------------------------------------------- backtest
def fig_backtest(retornos: pd.DataFrame, benchmark: str = "SPY") -> go.Figure:
    """Valor acumulado (escala log) y caída desde el máximo de cada estrategia (dos paneles, mismo eje x)."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.68, 0.32], vertical_spacing=0.06,
                        subplot_titles=("Valor de 1 USD invertido", "Caída desde el máximo"))
    for c in retornos.columns:
        r = retornos[c].fillna(0.0)
        valor = (1.0 + r).cumprod()
        dd = valor / valor.cummax() - 1.0
        es_bench = c == benchmark
        nombre = f"Benchmark ({c})" if es_bench else NOMBRES.get(c, c)
        color = COLOR_BENCHMARK if es_bench else _color(c)
        ancho = 2.5 if es_bench else 2
        fig.add_scatter(x=valor.index, y=valor, name=nombre, legendgroup=nombre, line={"color": color, "width": ancho},
                        hovertemplate=f"{nombre}: %{{y:.2f}}<extra></extra>", row=1, col=1)
        fig.add_scatter(x=dd.index, y=dd * 100, name=nombre, legendgroup=nombre, showlegend=False,
                        line={"color": color, "width": 1.5}, hovertemplate=f"{nombre}: %{{y:.1f}}%<extra></extra>",
                        row=2, col=1)
    fig.update_yaxes(type="log", title_text="USD (log)", row=1, col=1)
    fig.update_yaxes(title_text="%", row=2, col=1)
    fig.update_layout(hovermode="x unified", legend={"orientation": "h", "y": -0.08, "x": 0})
    fig = _estilo(fig, "Backtest walk-forward (con costos de rotación)", alto=720)
    for a in fig.layout.annotations:
        a.font = {"color": TINTA_2, "size": 12}
    return fig


def fig_ic(ic: pd.DataFrame) -> go.Figure:
    """IC de Spearman del score en cada rebalanceo (azul = el score acertó el orden, rojo = al revés)."""
    if ic is None or ic.empty:
        return _estilo(go.Figure(), "Capacidad predictiva del score (sin datos)")
    col = [AZUL if v >= 0 else ROJO for v in ic["ic_spearman"]]
    fig = go.Figure(go.Bar(x=ic["fecha"], y=ic["ic_spearman"], marker_color=col,
                           hovertemplate="%{x|%Y-%m-%d}: IC %{y:.2f}<extra></extra>"))
    fig.add_hline(y=float(ic["ic_spearman"].mean()), line={"color": TINTA_2, "width": 1.5},
                  annotation_text=f"IC medio {ic['ic_spearman'].mean():.2f}", annotation_position="top left",
                  annotation_font_color=TINTA_2)
    fig.update_layout(yaxis_title="IC de Spearman (score vs retorno siguiente)", bargap=0.3)
    return _estilo(fig, "¿El score anticipó los retornos del período siguiente?", alto=420, leyenda=False)


# ----------------------------------------------------------------------------------------------- ex-post
def fig_curvas_expost(curvas: pd.DataFrame, titulo: str) -> go.Figure:
    """Valor de 1 USD desde la fecha de la corrida, por portafolio y benchmark."""
    fig = go.Figure()
    for c in curvas.columns:
        es_bench = c.startswith("Benchmark")
        clave = _clave_por_nombre(c)
        fig.add_scatter(x=curvas.index, y=curvas[c], name=c,
                        line={"color": COLOR_BENCHMARK if es_bench else _color(clave), "width": 2.5 if es_bench else 2},
                        hovertemplate=f"{c}: %{{y:.3f}}<extra></extra>")
    fig.add_hline(y=1.0, line={"color": EJE, "width": 1})
    fig.update_layout(hovermode="x unified", yaxis_title="valor de 1 USD", legend={"orientation": "h", "y": -0.15, "x": 0})
    return _estilo(fig, titulo, alto=500)


def fig_ranking_expost(ranking: pd.DataFrame) -> go.Figure:
    """Exceso medio contra el benchmark por estrategia, en todas las corridas (azul gana, rojo pierde)."""
    if ranking is None or ranking.empty:
        return _estilo(go.Figure(), "Ranking de estrategias (sin corridas)")
    r = ranking.sort_values("exceso_medio")
    col = [AZUL if v >= 0 else ROJO for v in r["exceso_medio"]]
    fig = go.Figure(go.Bar(y=list(r.index), x=r["exceso_medio"] * 100, orientation="h", marker_color=col,
                           customdata=np.stack([r["corridas"], r["pct_le_gana_al_benchmark"] * 100], axis=1),
                           hovertemplate="<b>%{y}</b><br>exceso medio %{x:.2f}%<br>%{customdata[0]} corridas · "
                                         "le ganó al benchmark en %{customdata[1]:.0f}%<extra></extra>"))
    fig.add_vline(x=0, line={"color": EJE, "width": 1})
    fig.update_layout(xaxis_title="exceso medio vs benchmark (%)", bargap=0.3)
    return _estilo(fig, "Ranking de estrategias en todas las corridas", alto=max(360, 40 * len(r) + 140),
                   leyenda=False)


def fig_score_vs_retorno(senales: pd.DataFrame, retorno_bench: float | None = None) -> go.Figure:
    """Score de la corrida vs retorno posterior de cada activo (¿los de score alto rindieron más?)."""
    s = senales.dropna(subset=["score", "retorno_desde_corrida"])
    fig = go.Figure(go.Scatter(
        x=s["score"], y=s["retorno_desde_corrida"] * 100, mode="markers", text=list(s.index),
        marker={"size": 9, "color": AZUL, "line": {"color": SUPERFICIE, "width": 2}},
        customdata=s["clasificacion"] if "clasificacion" in s.columns else None,
        hovertemplate="<b>%{text}</b> (%{customdata})<br>score %{x:.0f} · retorno %{y:.1f}%<extra></extra>"))
    if retorno_bench is not None and np.isfinite(retorno_bench):
        fig.add_hline(y=retorno_bench * 100, line={"color": TINTA_2, "width": 1.5},
                      annotation_text=f"benchmark {retorno_bench:.1%}", annotation_font_color=TINTA_2)
    fig.update_layout(xaxis_title="score de oportunidad en la corrida", yaxis_title="retorno desde la corrida (%)")
    return _estilo(fig, "Score vs retorno posterior de cada activo", alto=460, leyenda=False)
