"""Salidas descargables: Excel (una hoja por tabla), reporte HTML con los gráficos interactivos y ZIP.

Cada notebook termina descargando un ZIP con todo (pedido habitual del usuario en sus proyectos). En la PC
se escribe en ``_descargas/`` del repo (ignorado por git); en Colab, en ``/content/_descargas``.
"""
from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path

import pandas as pd

from .config import RAIZ
from .registro import en_colab

# Columnas que se muestran como porcentaje en el Excel (por PREFIJO: "z_ret_3m" es un z-score, no un %).
PREFIJOS_PCT = ("ret_", "retorno", "volatilidad", "vol_", "max_drawdown", "drawdown", "var_95", "cvar_95", "peso",
                "exceso", "upside", "dist_", "fcf_yield", "rend_", "alfa", "rotacion", "pct_", "cobertura", "crec_",
                "margen", "gasto", "roe")


def _es_pct(nombre, serie) -> bool:
    return (str(nombre).lower().startswith(PREFIJOS_PCT) and serie is not None
            and pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie))


def carpeta_descargas() -> Path:
    d = Path("/content/_descargas") if en_colab() else RAIZ / "_descargas"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _nombre_hoja(nombre: str, usados: set) -> str:
    base = re.sub(r"[\[\]\*\?/\\:]", "_", nombre)[:31] or "hoja"
    n, k = base, 1
    while n in usados:
        k += 1
        n = f"{base[:28]}_{k}"
    usados.add(n)
    return n


def _limpiar_para_excel(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[c]):
            try:
                d[c] = d[c].dt.tz_localize(None)
            except (TypeError, AttributeError):
                pass
        elif d[c].dtype == object:
            d[c] = d[c].map(lambda x: ", ".join(map(str, x)) if isinstance(x, (list, tuple, set)) else x)
    if isinstance(d.index, pd.DatetimeIndex) and d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    return d


def excel_resultados(hojas: dict[str, pd.DataFrame], ruta: str | Path) -> Path:
    """Escribe un Excel con una hoja por tabla: encabezado fijo, anchos razonables y porcentajes."""
    from openpyxl.utils import get_column_letter

    ruta = Path(ruta)
    usados: set = set()
    with pd.ExcelWriter(ruta, engine="openpyxl") as xw:
        for nombre, df in hojas.items():
            if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                continue
            hoja = _nombre_hoja(nombre, usados)
            d = _limpiar_para_excel(df if isinstance(df, pd.DataFrame) else pd.DataFrame(df))
            con_indice = not isinstance(d.index, pd.RangeIndex)
            d.to_excel(xw, sheet_name=hoja, index=con_indice)
            ws = xw.sheets[hoja]
            ws.freeze_panes = "B2" if con_indice else "A2"
            if isinstance(d.columns, pd.MultiIndex):
                continue  # tablas raras: sin formato
            desplazamiento = 1 if con_indice else 0
            if con_indice:
                largo = max([len(str(d.index.name or ""))] + [len(str(v)) for v in d.index[:200]])
                ws.column_dimensions["A"].width = min(max(10, largo + 2), 40)
            for j, nombre_col in enumerate(d.columns, start=1 + desplazamiento):
                serie = d.iloc[:, j - 1 - desplazamiento]
                largo = max([len(str(nombre_col))] + [len(str(v)) for v in serie.head(200)])
                ws.column_dimensions[get_column_letter(j)].width = min(max(10, largo + 2), 60)
                if _es_pct(nombre_col, serie):
                    for fila in ws.iter_rows(min_row=2, min_col=j, max_col=j):
                        for celda in fila:
                            celda.number_format = "0.0%"
    return ruta


def reporte_html(titulo: str, bloques: list[tuple[str, object]], ruta: str | Path, nota: str = "") -> Path:
    """HTML autocontenido: ``bloques`` = [(subtítulo, figura plotly | DataFrame | texto)]. plotly.js va una
    sola vez dentro del archivo (se abre sin internet)."""
    from plotly.offline import get_plotlyjs

    partes = []
    for sub, obj in bloques:
        partes.append(f"<h2>{html.escape(sub)}</h2>")
        if hasattr(obj, "to_html") and hasattr(obj, "data") and hasattr(obj, "layout"):
            partes.append(obj.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False}))
        elif hasattr(obj, "to_html") and hasattr(obj, "data") and hasattr(obj, "format"):  # pandas Styler
            tabla = obj.set_table_attributes('class="tabla"').to_html()
            partes.append(f'<div class="tabla-scroll">{tabla}</div>')
        elif isinstance(obj, pd.DataFrame):
            tabla = obj.to_html(classes="tabla", float_format=lambda x: f"{x:,.4g}", na_rep="–", border=0)
            partes.append(f'<div class="tabla-scroll">{tabla}</div>')
        else:
            partes.append(f"<p>{html.escape(str(obj))}</p>")
    doc = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>{html.escape(titulo)}</title>
<script type="text/javascript">{get_plotlyjs()}</script>
<style>
body {{ font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: #0b0b0b; background: #f9f9f7;
       max-width: 1200px; margin: 0 auto; padding: 24px; }}
h1 {{ font-size: 24px; }} h2 {{ font-size: 18px; margin-top: 36px; color: #0b0b0b; }}
p.nota {{ color: #52514e; font-size: 14px; }}
table.tabla {{ border-collapse: collapse; font-size: 12px; font-variant-numeric: tabular-nums; }}
table.tabla th, table.tabla td {{ padding: 4px 8px; border-bottom: 1px solid #e1e0d9; text-align: right;
                                 white-space: nowrap; }}
div.tabla-scroll {{ overflow-x: auto; }}
table.tabla th {{ color: #52514e; }}
</style></head><body>
<h1>{html.escape(titulo)}</h1>
<p class="nota">{html.escape(nota)}</p>
{''.join(partes)}
</body></html>"""
    ruta = Path(ruta)
    ruta.write_text(doc, encoding="utf-8")
    return ruta


def zip_archivos(archivos: list[Path], ruta_zip: str | Path, carpetas: list[Path] | None = None) -> Path:
    """Arma un ZIP con archivos sueltos y carpetas completas (con su nombre como prefijo)."""
    ruta_zip = Path(ruta_zip)
    with zipfile.ZipFile(ruta_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for a in archivos:
            if a and Path(a).exists():
                z.write(a, arcname=Path(a).name)
        for c in carpetas or []:
            c = Path(c)
            if c.exists():
                for f in sorted(c.rglob("*")):
                    if f.is_file():
                        z.write(f, arcname=str(Path(c.name) / f.relative_to(c)))
    return ruta_zip


def descargar_en_colab(ruta: str | Path) -> None:
    """En Colab dispara la descarga del archivo al navegador; en la PC no hace nada."""
    if en_colab():
        from google.colab import files  # type: ignore

        files.download(str(ruta))
