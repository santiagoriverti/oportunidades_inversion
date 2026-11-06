"""Fundamentales de Yahoo Finance (``Ticker.info``): valuación de acciones y datos de ETFs.

Es una FOTO actual (Yahoo gratis no da la historia de los múltiplos): sirve para el score de hoy, no para
el backtest. Cuidado con las unidades de Yahoo (ver CONTEXTO.md §5):
- ``dividendYield`` viene en PORCENTAJE (5.02 = 5,02%): no se usa. Para acciones se usa
  ``dividendRate / precio`` (dividendo anual en la moneda de cotización) y, si falta,
  ``trailingAnnualDividendYield`` (fracción); para ETFs, ``yield`` (fracción).
- ADRs que reportan en otra moneda (VALE: ``financialCurrency`` = BRL, cotiza en USD): Yahoo mezcla monedas
  en el EPS trailing, el flujo de caja y el dividendo trailing (VALE daba 49% de dividendo). Para esos se
  descartan P/E trailing, PEG, P/E relativo al sector y FCF yield (columna ``monedas_mezcladas``).
- ``netExpenseRatio`` de los ETFs viene en porcentaje (0.0945 = 0,0945% anual) -> se divide por 100.

Métricas derivadas (solo acciones):
    upside_analistas    precio objetivo promedio / precio actual - 1 (si hay 3+ analistas)
    pe_relativo_sector  P/E trailing / P/E trailing del ETF SPDR del sector (XLK, XLV...)
    fcf_yield           flujo de caja libre / capitalización
    peg                 P/E / crecimiento esperado (solo si es positivo)
    crec_implicito      P/E trailing / P/E forward - 1 (crecimiento de ganancias que espera el mercado)
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from .datos import _yf, descargar_paralelo

# Sector de Yahoo -> ETF sectorial SPDR (referencia de P/E del sector).
ETF_SECTOR = {
    "Technology": "XLK", "Healthcare": "XLV", "Financial Services": "XLF", "Energy": "XLE",
    "Consumer Defensive": "XLP", "Consumer Cyclical": "XLY", "Industrials": "XLI",
    "Communication Services": "XLC", "Basic Materials": "XLB", "Utilities": "XLU", "Real Estate": "XLRE",
}

CAMPOS = ["quoteType", "longName", "shortName", "currency", "financialCurrency", "sector", "industry",
          "marketCap", "trailingPE", "forwardPE", "trailingPegRatio", "pegRatio", "priceToBook",
          "enterpriseToEbitda", "freeCashflow", "dividendRate", "trailingAnnualDividendYield", "yield",
          "targetMeanPrice", "currentPrice", "regularMarketPrice",
          "recommendationMean", "numberOfAnalystOpinions", "beta", "earningsGrowth", "revenueGrowth",
          "profitMargins", "returnOnEquity", "netExpenseRatio", "totalAssets", "fiftyTwoWeekHigh",
          "fiftyTwoWeekLow"]


def _num(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return np.nan
    return v if np.isfinite(v) else np.nan


def descargar_info(simbolos: list[str], max_workers: int = 6, reintentos: int = 2) -> dict[str, dict]:
    """``Ticker.info`` de cada símbolo (solo los CAMPOS), en paralelo y con reintentos. Los que fallan
    quedan como diccionario vacío."""
    yf = _yf()

    def uno(s: str) -> dict:
        for i in range(reintentos + 1):
            try:
                info = yf.Ticker(s).info or {}
                if info:
                    return {k: info.get(k) for k in CAMPOS}
            except Exception:  # noqa: BLE001 - rate limit o símbolo raro: reintentar
                pass
            time.sleep(1.5 * (i + 1))
        return {}

    return descargar_paralelo(uno, list(dict.fromkeys(simbolos)), max_workers=max_workers)


def tabla_fundamentales(info: dict[str, dict], info_sectores: dict[str, dict] | None = None) -> pd.DataFrame:
    """Tabla de fundamentales (una fila por símbolo) a partir de lo que devolvió ``descargar_info``.

    ``info_sectores``: info de los ETFs sectoriales (si no está en ``info``) para el P/E relativo.
    """
    info_sectores = {**(info_sectores or {}), **info}
    pe_sector = {etf: _num(info_sectores.get(etf, {}).get("trailingPE")) for etf in ETF_SECTOR.values()}
    filas = {}
    for s, d in info.items():
        qt = (d.get("quoteType") or "").upper()
        precio = _num(d.get("currentPrice"))
        if np.isnan(precio):
            precio = _num(d.get("regularMarketPrice"))
        pe_t = _num(d.get("trailingPE"))
        pe_f = _num(d.get("forwardPE"))
        peg = _num(d.get("trailingPegRatio"))
        if np.isnan(peg):
            peg = _num(d.get("pegRatio"))
        mcap = _num(d.get("marketCap"))
        fcf = _num(d.get("freeCashflow"))
        n_an = _num(d.get("numberOfAnalystOpinions"))
        target = _num(d.get("targetMeanPrice"))
        sector = d.get("sector") or ""
        etf_sec = ETF_SECTOR.get(sector, "")
        pe_ref = pe_sector.get(etf_sec, np.nan) if etf_sec else np.nan
        es_accion = qt == "EQUITY"
        mon, mon_fin = (d.get("currency") or ""), (d.get("financialCurrency") or "")
        mezcla = bool(es_accion and mon and mon_fin and mon.upper() != mon_fin.upper())
        div_rate = _num(d.get("dividendRate"))
        if es_accion:
            if div_rate >= 0 and precio > 0:
                rend_div = div_rate / precio
            elif not mezcla:
                rend_div = _num(d.get("trailingAnnualDividendYield"))
            else:
                rend_div = np.nan
        else:
            rend_div = _num(d.get("yield"))
        fila = {
            "tipo_yahoo": qt,
            "nombre_yahoo": d.get("longName") or d.get("shortName") or "",
            "sector": sector,
            "industria": d.get("industry") or "",
            "etf_sector": etf_sec,
            "market_cap": mcap,
            "pe_trailing": pe_t if pe_t > 0 else np.nan,
            "pe_forward": pe_f if pe_f > 0 else np.nan,
            "peg": peg if peg > 0 else np.nan,
            "precio_valor_libros": _num(d.get("priceToBook")),
            "ev_ebitda": _num(d.get("enterpriseToEbitda")),
            "fcf_yield": fcf / mcap if es_accion and mcap and mcap > 0 and np.isfinite(fcf) else np.nan,
            "rend_dividendo": rend_div,
            "monedas_mezcladas": mezcla,
            "precio_objetivo": target,
            "upside_analistas": (target / precio - 1) if (es_accion and n_an >= 3 and target > 0 and precio > 0)
            else np.nan,
            "recomendacion": _num(d.get("recommendationMean")),  # 1 = compra fuerte ... 5 = venta
            "n_analistas": n_an,
            "beta_yahoo": _num(d.get("beta")),
            "crec_ganancias": _num(d.get("earningsGrowth")),
            "crec_ventas": _num(d.get("revenueGrowth")),
            "margen_neto": _num(d.get("profitMargins")),
            "roe": _num(d.get("returnOnEquity")),
            "gasto_anual_etf": _num(d.get("netExpenseRatio")) / 100.0,
            "activos_etf": _num(d.get("totalAssets")),
        }
        fila["pe_relativo_sector"] = (fila["pe_trailing"] / pe_ref) if es_accion and pe_ref and pe_ref > 0 \
            else np.nan
        fila["crec_implicito"] = (fila["pe_trailing"] / fila["pe_forward"] - 1) if es_accion else np.nan
        if mezcla:  # EPS trailing y flujo de caja en otra moneda que el precio: no son comparables
            for k in ("pe_trailing", "peg", "pe_relativo_sector", "crec_implicito", "fcf_yield"):
                fila[k] = np.nan
        if not es_accion:  # métricas de valuación de empresa no aplican a ETFs/cripto/índices
            for k in ("peg", "fcf_yield", "ev_ebitda", "precio_valor_libros", "pe_forward", "crec_implicito"):
                fila[k] = np.nan
        filas[s] = fila
    df = pd.DataFrame.from_dict(filas, orient="index")
    df.index.name = "activo"
    return df


def obtener_fundamentales(simbolos: list[str], max_workers: int = 6) -> tuple[pd.DataFrame, list[str]]:
    """Baja la info de los símbolos y de los ETFs sectoriales que hagan falta. Devuelve (tabla, avisos)."""
    avisos = []
    info = descargar_info(simbolos, max_workers=max_workers)
    sin_info = [s for s, d in info.items() if not d]
    if sin_info:
        avisos.append(f"Sin fundamentales de Yahoo para {len(sin_info)} activos: {', '.join(sin_info[:15])}"
                      + ("..." if len(sin_info) > 15 else ""))
    sectores = {d.get("sector") for d in info.values() if d and (d.get("quoteType") or "").upper() == "EQUITY"}
    etfs = sorted({ETF_SECTOR[s] for s in sectores if s in ETF_SECTOR} - set(info))
    info_sec = descargar_info(etfs, max_workers=max_workers) if etfs else {}
    tabla = tabla_fundamentales(info, info_sec)
    return tabla, avisos
