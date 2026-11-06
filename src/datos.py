"""Datos de mercado: precios (Yahoo Finance vía yfinance), conversión a USD, calidad, tasa libre de riesgo
y cotizaciones de CEDEARs (data912).

Convenciones (ver CONTEXTO.md §2 y §5):
- Precios de cierre AJUSTADOS por dividendos y splits (``auto_adjust=True``): los retornos son totales.
- Calendario de días hábiles (lunes a viernes). Los feriados de cada bolsa se completan con el último
  precio (hasta 5 días); BTC pierde los fines de semana (su movimiento del finde cae en el lunes).
- Todo se expresa en USD: los activos en otra moneda se multiplican por el tipo de cambio de Yahoo
  (``EURUSD=X``...). Peniques (GBp) se dividen por 100.
- Yahoo ajusta hacia atrás los precios cuando hay dividendos: nunca comparar precios ajustados bajados en
  días distintos (el seguimiento ex-post vuelve a bajar todo; ver expost.py).
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

URL_CEDEARS = "https://data912.com/live/arg_cedears"
TASA_LIBRE_RIESGO_DEFECTO = 0.04


def _yf():
    """Importa yfinance recién cuando hace falta (los tests no lo necesitan)."""
    import yfinance as yf

    return yf


def _indice_fechas(idx) -> pd.DatetimeIndex:
    idx = pd.to_datetime(idx)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return idx.normalize()


def _extraer_cierres(df: pd.DataFrame, simbolos: list[str]) -> pd.DataFrame:
    """Columna de cierre de lo que devuelve yf.download, sea MultiIndex (Price, Ticker) o simple."""
    if df is None or len(df) == 0:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        n0 = df.columns.get_level_values(0)
        n1 = df.columns.get_level_values(1)
        if "Close" in n0:
            c = df["Close"]
        elif "Adj Close" in n0:
            c = df["Adj Close"]
        elif "Close" in n1:  # group_by="ticker"
            c = df.xs("Close", axis=1, level=1)
        else:
            return pd.DataFrame()
    else:
        col = "Close" if "Close" in df.columns else ("Adj Close" if "Adj Close" in df.columns else None)
        if col is None:
            return pd.DataFrame()
        c = df[[col]].rename(columns={col: simbolos[0]})
    if isinstance(c, pd.Series):
        c = c.to_frame(simbolos[0])
    c = c.copy()
    c.columns = [str(x) for x in c.columns]
    c.index = _indice_fechas(c.index)
    c = c[~c.index.duplicated(keep="last")]
    return c.apply(pd.to_numeric, errors="coerce").astype(float)


def descargar_cierres(simbolos: list[str], inicio, fin=None, reintentos: int = 2,
                      pausa: float = 2.0) -> tuple[pd.DataFrame, list[str]]:
    """Cierres ajustados diarios de Yahoo. Devuelve (DataFrame fecha x símbolo, símbolos sin datos).

    Baja todo junto y reintenta de a uno los que fallaron (Yahoo a veces corta algunos pedidos).
    """
    yf = _yf()
    simbolos = list(dict.fromkeys(s for s in simbolos if s))
    if not simbolos:
        return pd.DataFrame(), []
    kw = dict(start=pd.Timestamp(inicio).strftime("%Y-%m-%d"), auto_adjust=True, progress=False)
    if fin is not None:
        kw["end"] = pd.Timestamp(fin).strftime("%Y-%m-%d")
    try:
        crudo = yf.download(simbolos, threads=True, **kw)
        cierres = _extraer_cierres(crudo, simbolos)
    except Exception as e:  # noqa: BLE001 - se reintenta de a uno
        print(f"  aviso: la descarga conjunta falló ({type(e).__name__}); se reintenta de a uno")
        cierres = pd.DataFrame()

    def vacio(s):
        return s not in cierres.columns or cierres[s].dropna().empty

    faltan = [s for s in simbolos if vacio(s)]
    for intento in range(reintentos):
        if not faltan:
            break
        time.sleep(pausa * (intento + 1))
        for s in list(faltan):
            try:
                c = _extraer_cierres(yf.download(s, threads=False, **kw), [s])
            except Exception:  # noqa: BLE001
                continue
            if s in c.columns and not c[s].dropna().empty:
                cierres = c[[s]] if cierres.empty else cierres.join(c[[s]], how="outer")
                faltan.remove(s)
    if not cierres.empty:
        cierres = cierres[[s for s in simbolos if s in cierres.columns and not cierres[s].dropna().empty]]
        cierres = cierres.sort_index()
    return cierres, faltan


def alinear_dias_habiles(cierres: pd.DataFrame, limite_ffill: int = 5) -> pd.DataFrame:
    """Lleva todo a días hábiles (lun-vie): completa feriados con el último precio (hasta ``limite_ffill``
    días) y descarta sábados y domingos. No inventa precios antes del primer dato ni después de 5 días sin
    datos (un activo que deja de cotizar queda en NaN)."""
    if cierres.empty:
        return cierres
    idx = pd.bdate_range(cierres.index.min(), cierres.index.max())
    union = cierres.index.union(idx)
    return cierres.reindex(union).ffill(limit=limite_ffill).reindex(idx)


def aplicar_inicio_valido(precios: pd.DataFrame, inicios: dict[str, str]) -> pd.DataFrame:
    """Pone NaN antes de la fecha de inicio válida de cada activo (historia de SPAC, cambios de ticker...)."""
    p = precios.copy()
    for s, f in inicios.items():
        if f and s in p.columns:
            p.loc[p.index < pd.Timestamp(f), s] = np.nan
    return p


def detectar_monedas(simbolos: list[str], conocidas: dict[str, str] | None = None) -> dict[str, str]:
    """Moneda de cotización de cada símbolo: la conocida (CSV), la del sufijo, o la que informa Yahoo."""
    from .universo import moneda_por_sufijo

    conocidas = conocidas or {}
    out, preguntar = {}, []
    for s in simbolos:
        m = (conocidas.get(s) or "").strip() or moneda_por_sufijo(s)
        if m:
            out[s] = m
        else:
            preguntar.append(s)
    if preguntar:
        yf = _yf()
        for s in preguntar:
            try:
                fi = yf.Ticker(s).fast_info
                m = fi.get("currency") if hasattr(fi, "get") else getattr(fi, "currency", None)
            except Exception:  # noqa: BLE001
                m = None
            out[s] = m or "USD"
            if not m:
                print(f"  aviso: no se pudo saber la moneda de {s}; se asume USD")
    return out


def _par_fx(moneda: str) -> tuple[str, float]:
    """Símbolo de Yahoo del tipo de cambio a USD y divisor (peniques -> libras)."""
    if moneda in ("GBp", "GBX"):
        return "GBPUSD=X", 100.0
    if moneda == "ILA":  # agorot israelíes
        return "ILSUSD=X", 100.0
    return f"{moneda.upper()}USD=X", 1.0


def convertir_a_usd(precios: pd.DataFrame, monedas: dict[str, str], inicio,
                    fx: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Convierte a USD las columnas que cotizan en otra moneda. ``fx`` permite pasar los tipos de cambio ya
    descargados (tests). Devuelve (precios en USD, avisos)."""
    avisos = []
    otras = {s: m for s, m in monedas.items() if s in precios.columns and m and m.upper() != "USD"}
    if not otras:
        return precios, avisos
    pares = {s: _par_fx(m) for s, m in otras.items()}
    if fx is None:
        fx, faltan = descargar_cierres(sorted({p for p, _ in pares.values()}), inicio)
        if faltan:
            avisos.append(f"No se pudo bajar el tipo de cambio {faltan}")
        fx = alinear_dias_habiles(fx) if not fx.empty else fx
    p = precios.copy()
    for s, (par, divisor) in pares.items():
        if fx is None or par not in fx.columns:
            avisos.append(f"{s} cotiza en {otras[s]} y no hay tipo de cambio {par}: queda fuera")
            p[s] = np.nan
            continue
        tc = fx[par].reindex(fx.index.union(p.index)).ffill(limit=5).reindex(p.index)
        p[s] = p[s] * tc / divisor
        if otras[s].upper() == "ARS":
            avisos.append(f"{s} cotiza en pesos: se convirtió con el dólar oficial de Yahoo (no MEP/CCL)")
    return p, avisos


def reporte_calidad(cierres_crudos: pd.DataFrame, precios: pd.DataFrame, inicio_ventana,
                    fecha_ref=None) -> pd.DataFrame:
    """Una fila por activo: primera y última fecha con dato, años de historia, cobertura de la ventana de
    optimización y días hábiles desde el último precio (para detectar activos que dejaron de cotizar)."""
    fecha_ref = pd.Timestamp(fecha_ref) if fecha_ref is not None else precios.index.max()
    inicio_ventana = pd.Timestamp(inicio_ventana)
    filas = []
    for s in precios.columns:
        valido = precios[s].dropna()
        crudo = cierres_crudos[s].dropna() if s in cierres_crudos.columns else valido
        if valido.empty:
            filas.append({"activo": s, "observaciones": 0})
            continue
        vent = precios.loc[precios.index >= inicio_ventana, s]
        ultimo = crudo.index.max() if not crudo.empty else valido.index.max()
        filas.append({
            "activo": s,
            "primera_fecha": valido.index.min().date(),
            "ultima_fecha": ultimo.date(),
            "observaciones": int(valido.size),
            "anios_historia": round((valido.index.max() - valido.index.min()).days / 365.25, 2),
            "cobertura_ventana": round(float(vent.notna().mean()) if len(vent) else 0.0, 3),
            "dias_sin_dato": int(max(len(pd.bdate_range(ultimo, fecha_ref)) - 1, 0)),
        })
    df = pd.DataFrame(filas).set_index("activo")
    return df


def tasa_libre_riesgo(inicio="2010-01-01") -> tuple[float, pd.Series, str]:
    """Tasa anual del T-bill de 13 semanas (^IRX de Yahoo, en %): (último valor, serie diaria, fuente).
    Si Yahoo falla usa 4% y lo avisa."""
    try:
        df, _ = descargar_cierres(["^IRX"], inicio)
        s = (df["^IRX"].dropna() / 100.0) if "^IRX" in df.columns else pd.Series(dtype=float)
    except Exception:  # noqa: BLE001
        s = pd.Series(dtype=float)
    if s.empty or not np.isfinite(s.iloc[-1]):
        return TASA_LIBRE_RIESGO_DEFECTO, pd.Series(dtype=float), "valor por defecto (4%): falló ^IRX"
    return float(s.iloc[-1]), s, f"^IRX (T-bill 13 semanas) al {s.index[-1].date()}"


def cotizaciones_cedears(timeout: float = 20.0) -> tuple[pd.DataFrame | None, float | None, str]:
    """Cotizaciones en vivo de CEDEARs de data912 (BYMA). Devuelve (tabla, dólar MEP implícito, mensaje).

    La tabla tiene una fila por especie (``SPY`` en pesos, ``SPYD`` en dólares MEP...). El MEP implícito
    es la mediana de precio_pesos / precio_D entre los CEDEARs que tienen las dos especies con operaciones:
    sirve para pasar a dólares los CEDEARs que solo cotizan en pesos.
    """
    try:
        import requests

        r = requests.get(URL_CEDEARS, timeout=timeout, headers={"User-Agent": "oportunidades_inversion"})
        r.raise_for_status()
        datos = r.json()
        tabla = pd.DataFrame(datos)
    except Exception as e:  # noqa: BLE001
        return None, None, f"data912 no respondió ({type(e).__name__}): no se calculan cantidades de CEDEARs"
    if tabla.empty or "symbol" not in tabla.columns or "c" not in tabla.columns:
        return None, None, "data912 devolvió un formato inesperado: no se calculan cantidades de CEDEARs"
    tabla["symbol"] = tabla["symbol"].astype(str).str.upper()
    for c in ("c", "v", "px_bid", "px_ask"):
        if c in tabla.columns:
            tabla[c] = pd.to_numeric(tabla[c], errors="coerce")
    tabla = tabla.drop_duplicates("symbol").set_index("symbol")
    ratios = []
    for s in tabla.index:
        if s.endswith("D") and s[:-1] in tabla.index:
            pd_, pa = tabla.at[s, "c"], tabla.at[s[:-1], "c"]
            vol = tabla.at[s, "v"] if "v" in tabla.columns else np.nan
            if pd_ and pa and pd_ > 0 and pa > 0 and (not np.isfinite(vol) or vol > 0):
                ratios.append(pa / pd_)
    mep = float(np.median(ratios)) if len(ratios) >= 5 else None
    msg = f"data912: {len(tabla)} especies de CEDEARs" + (f"; MEP implícito {mep:,.1f}" if mep else "")
    return tabla, mep, msg


def descargar_paralelo(funcion, items: list, max_workers: int = 6) -> dict:
    """Aplica ``funcion`` a cada item en hilos (para las consultas de a un ticker a Yahoo)."""
    out = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for item, res in zip(items, ex.map(funcion, items)):
            out[item] = res
    return out
