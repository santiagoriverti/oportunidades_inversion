"""Universo de activos: lista de tickers, símbolo de Yahoo, moneda, CEDEAR y estado de cada uno.

La lista por defecto es ``data/universo.csv`` (la lista original del usuario, con las correcciones
documentadas en la columna ``nota``). En el notebook se puede pasar otra lista: los tickers que ya están en
el CSV toman sus datos de ahí; los nuevos se normalizan con ``ALIAS`` y la moneda se deduce del sufijo o se
consulta a Yahoo (``datos.detectar_monedas``).

Columnas del CSV:
    ticker               como lo escribió el usuario (BRKB, BTC, VGII...)
    yahoo                símbolo en Yahoo Finance (BRK-B, BTC-USD, VGIT...); vacío = no hay datos
    nombre, rubro        descripción
    tipo                 accion | etf | cripto | indice | bono | on | fondo
    moneda               moneda de cotización en Yahoo (USD, EUR...): todo se convierte a USD
    inicio_valido        AAAA-MM-DD: se descartan precios anteriores (p.ej. historia de un SPAC)
    cedear               símbolo del CEDEAR en BYMA si difiere del ticker de EE.UU. (BRKB, GOOGL)
    estado               activo | referencia (se muestra, no se invierte) | excluido (no se descarga)
    nota                 correcciones y advertencias
    comentario_original  comentario que venía en la lista original
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .config import RUTA_UNIVERSO

COLUMNAS = ["ticker", "yahoo", "nombre", "rubro", "tipo", "moneda", "inicio_valido", "cedear", "estado", "nota",
            "comentario_original"]
ESTADOS = ("activo", "referencia", "excluido")
TIPOS = ("accion", "etf", "cripto", "indice", "bono", "on", "fondo", "")

# Nombres alternativos frecuentes -> símbolo de Yahoo Finance.
ALIAS = {
    "BRKB": "BRK-B", "BRK.B": "BRK-B", "BRK/B": "BRK-B",
    "BRKA": "BRK-A", "BRK.A": "BRK-A", "BRK/A": "BRK-A",
    "BFB": "BF-B", "BF.B": "BF-B",
    "BTC": "BTC-USD", "BITCOIN": "BTC-USD",
    "ETH": "ETH-USD", "ETHEREUM": "ETH-USD",
    "SOL": "SOL-USD", "ADA": "ADA-USD", "XRP": "XRP-USD", "DOGE": "DOGE-USD",
    "IXIC": "^IXIC", "NDX": "^NDX", "GSPC": "^GSPC", "SPX": "^GSPC", "DJI": "^DJI", "VIX": "^VIX",
}

# Moneda según el sufijo de Yahoo (.L se consulta a Yahoo: en Londres hay ETFs en USD, GBP y peniques).
SUFIJO_MONEDA = {
    ".DE": "EUR", ".F": "EUR", ".PA": "EUR", ".AS": "EUR", ".MI": "EUR", ".MC": "EUR", ".BR": "EUR",
    ".LS": "EUR", ".VI": "EUR", ".HE": "EUR", ".IR": "EUR", ".SW": "CHF", ".TO": "CAD", ".V": "CAD",
    ".SA": "BRL", ".MX": "MXN", ".BA": "ARS", ".T": "JPY", ".HK": "HKD", ".AX": "AUD",
}

TIPO_POR_QUOTETYPE = {"EQUITY": "accion", "ETF": "etf", "CRYPTOCURRENCY": "cripto", "INDEX": "indice",
                      "MUTUALFUND": "fondo"}


def normalizar_ticker(t: str) -> str:
    """Mayúsculas, sin espacios; aplica ALIAS (BRKB -> BRK-B, BTC -> BTC-USD...)."""
    s = re.sub(r"\s+", "", str(t)).upper()
    return ALIAS.get(s, s)


def moneda_por_sufijo(simbolo: str) -> str | None:
    """USD para símbolos de EE.UU., cripto (-USD) e índices; la del sufijo si se conoce; None si hay que
    preguntarle a Yahoo (.L u otro sufijo desconocido)."""
    s = simbolo.upper()
    if s.startswith("^") or s.endswith("-USD") or "." not in s:
        return "USD"
    for suf, mon in SUFIJO_MONEDA.items():
        if s.endswith(suf):
            return mon
    return None


def cedear_por_defecto(simbolo: str) -> str:
    """Símbolo de CEDEAR que se prueba si el CSV no dice otra cosa: el ticker de EE.UU. sin guiones.
    Símbolos con sufijo de otra bolsa, cripto o índices no tienen CEDEAR."""
    s = simbolo.upper()
    if s.startswith("^") or "." in s or "=" in s or s.endswith("-USD"):
        return ""
    return s.replace("-", "")


def cargar_universo(ruta: str | Path = RUTA_UNIVERSO) -> pd.DataFrame:
    """Lee el CSV del universo y valida columnas y valores."""
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8")
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise ValueError(f"{ruta}: faltan columnas {faltan}")
    df = df[COLUMNAS].copy()
    for c in COLUMNAS:
        df[c] = df[c].astype(str).str.strip()
    df["ticker"] = df["ticker"].str.upper()
    df["yahoo"] = df["yahoo"].str.upper()
    df["cedear"] = df["cedear"].str.upper()
    df["estado"] = df["estado"].str.lower().replace("", "activo")
    df["tipo"] = df["tipo"].str.lower()
    df["moneda"] = df["moneda"].str.upper()
    malos = sorted(set(df["estado"]) - set(ESTADOS))
    if malos:
        raise ValueError(f"{ruta}: estados desconocidos {malos} (válidos: {ESTADOS})")
    dup = df["ticker"][df["ticker"].duplicated()].tolist()
    if dup:
        raise ValueError(f"{ruta}: tickers repetidos {dup}")
    for f in df.loc[df["inicio_valido"] != "", "inicio_valido"]:
        pd.Timestamp(f)  # frena si la fecha está mal escrita
    sin_yahoo = df[(df["estado"] != "excluido") & (df["yahoo"] == "")]
    if not sin_yahoo.empty:
        raise ValueError(f"{ruta}: {sin_yahoo['ticker'].tolist()} no están excluidos pero no tienen símbolo de Yahoo")
    return df.reset_index(drop=True)


def resolver_universo(tickers: list[str] | None = None, ruta: str | Path = RUTA_UNIVERSO) -> pd.DataFrame:
    """Devuelve el universo a analizar (mismas columnas que el CSV, una fila por ticker pedido).

    - ``tickers=None``: todo el CSV (los excluidos quedan en la tabla para que se vea el motivo).
    - Lista propia: cada ticker se busca en el CSV por ``ticker`` o por ``yahoo``; si no está, se crea una
      fila con el símbolo normalizado. Los repetidos (BTC y BTC-USD, por ejemplo) se informan una sola vez.
    """
    base = cargar_universo(ruta)
    if tickers is None:
        return base
    filas, vistos = [], set()
    por_ticker = {r.ticker: r for r in base.itertuples(index=False)}
    por_yahoo = {r.yahoo: r for r in base.itertuples(index=False) if r.yahoo}
    for t in tickers:
        crudo = re.sub(r"\s+", "", str(t)).upper()
        if not crudo:
            continue
        fila = por_ticker.get(crudo) or por_yahoo.get(crudo)
        if fila is None:
            simb = normalizar_ticker(crudo)
            fila = por_yahoo.get(simb) or por_ticker.get(simb)
        if fila is not None:
            d = fila._asdict()
        else:
            simb = normalizar_ticker(crudo)
            d = {c: "" for c in COLUMNAS}
            d.update(ticker=crudo, yahoo=simb, nombre=simb, estado="activo",
                     moneda=moneda_por_sufijo(simb) or "", tipo="indice" if simb.startswith("^") else "")
            if simb.startswith("^"):
                d["estado"] = "referencia"
                d["nota"] = "Índice: se muestra como referencia, no se puede comprar."
        clave = d["yahoo"] or d["ticker"]
        if clave in vistos:
            continue
        vistos.add(clave)
        filas.append(d)
    if not filas:
        raise ValueError("La lista de tickers está vacía")
    return pd.DataFrame(filas, columns=COLUMNAS).reset_index(drop=True)


def activos(universo: pd.DataFrame) -> list[str]:
    """Símbolos de Yahoo de los activos invertibles (estado == activo)."""
    return universo.loc[universo["estado"] == "activo", "yahoo"].tolist()


def referencias(universo: pd.DataFrame) -> list[str]:
    return universo.loc[universo["estado"] == "referencia", "yahoo"].tolist()


def mapa(universo: pd.DataFrame, columna: str) -> dict[str, str]:
    """Diccionario símbolo de Yahoo -> valor de la columna (solo filas con símbolo)."""
    u = universo[universo["yahoo"] != ""]
    return dict(zip(u["yahoo"], u[columna]))


def mapa_cedears(universo: pd.DataFrame) -> dict[str, str]:
    """Símbolo de Yahoo -> símbolo de CEDEAR a probar (columna cedear o el ticker sin guiones)."""
    out = {}
    for r in universo[universo["yahoo"] != ""].itertuples(index=False):
        out[r.yahoo] = r.cedear or cedear_por_defecto(r.yahoo)
    return out
