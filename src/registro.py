"""Registro de corridas: cada análisis queda guardado para medir después cómo le fue (seguimiento ex-post).

Dónde (decisión del usuario 2026-11-06): Google Drive en Colab
(``Mi unidad/oportunidades_inversion/registros``); en la PC, ``registros_local/`` (ignorado por git).

Una carpeta por corrida, ``AAAAMMDD_HHMMSS`` (hora de Argentina), con:
    metadata.json            fecha y hora, fecha de los datos, versión del código, parámetros, universo,
                             excluidos, gemelos, tasa libre de riesgo, ventana
    senales.csv              score, clasificación, señales e indicadores de cada activo
    pesos.csv                formato largo: portafolio, activo, peso
    resumen_portafolios.csv  retorno esperado, volatilidad, Sharpe ex-ante de cada portafolio
    asignacion.csv           cantidades a comprar (portafolio, vehículo, activo, cantidad, precio, monto)
    precios.csv              precio de cada activo en la fecha de los datos (USD)
Formato detallado en docs/ARQUITECTURA.md §4.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__
from .config import RAIZ

CARPETA_DRIVE = "/content/drive/MyDrive/oportunidades_inversion/registros"
CARPETA_LOCAL = RAIZ / "registros_local"
ZONA = "America/Argentina/Buenos_Aires"


def en_colab() -> bool:
    return "google.colab" in sys.modules


def montar_drive() -> bool:
    """Monta Google Drive en Colab (pide autorización la primera vez). Devuelve True si quedó montado."""
    if not en_colab():
        return False
    try:
        from google.colab import drive  # type: ignore

        drive.mount("/content/drive")
        return Path("/content/drive/MyDrive").exists()
    except Exception as e:  # noqa: BLE001
        print(f"No se pudo montar Google Drive ({type(e).__name__}): se guarda en /content (se pierde al cerrar)")
        return False


def carpeta_por_defecto(montar: bool = True) -> Path:
    """Drive en Colab (si se puede montar), ``registros_local/`` en la PC."""
    if en_colab():
        if montar and montar_drive():
            return Path(CARPETA_DRIVE)
        return Path("/content/registros")
    return CARPETA_LOCAL


def ahora_argentina() -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(ZONA))
    except Exception:  # noqa: BLE001 - sin base de zonas horarias: hora local
        return datetime.now().astimezone()


def version_repo() -> str:
    try:
        out = subprocess.run(["git", "-C", str(RAIZ), "log", "-1", "--format=%h %ad", "--date=short"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "sin git"
    except Exception:  # noqa: BLE001
        return "sin git"


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.isoformat()
    if isinstance(o, (set, tuple)):
        return list(o)
    if isinstance(o, Path):
        return str(o)
    return str(o)


def guardar_corrida(carpeta: str | Path, metadata: dict, senales: pd.DataFrame, pesos: dict[str, pd.Series],
                    resumen: pd.DataFrame, asignacion: pd.DataFrame | None, precios: pd.Series) -> Path:
    """Guarda una corrida y devuelve su carpeta."""
    momento = ahora_argentina()
    base = Path(carpeta)
    base.mkdir(parents=True, exist_ok=True)
    run_id = momento.strftime("%Y%m%d_%H%M%S")
    destino = base / run_id
    k = 1
    while destino.exists():
        k += 1
        destino = base / f"{run_id}_{k}"
    destino.mkdir(parents=True)
    meta = dict(metadata)
    meta.update(run_id=destino.name, fecha_hora=momento.isoformat(timespec="seconds"),
                version_codigo=__version__, version_repo=version_repo())
    (destino / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=_json_default),
                                           encoding="utf-8")
    senales.to_csv(destino / "senales.csv", encoding="utf-8")
    filas = [{"portafolio": k_, "activo": s, "peso": float(v)}
             for k_, w in pesos.items() if w is not None for s, v in w.items() if v > 0]
    pd.DataFrame(filas, columns=["portafolio", "activo", "peso"]).to_csv(destino / "pesos.csv", index=False,
                                                                       encoding="utf-8")
    resumen.to_csv(destino / "resumen_portafolios.csv", encoding="utf-8")
    if asignacion is not None and not asignacion.empty:
        asignacion.to_csv(destino / "asignacion.csv", index=False, encoding="utf-8")
    precios.rename("precio").to_frame().rename_axis("activo").to_csv(destino / "precios.csv", encoding="utf-8")
    return destino


def listar_corridas(carpeta: str | Path) -> pd.DataFrame:
    """Tabla con las corridas guardadas en la carpeta (más vieja primero)."""
    base = Path(carpeta)
    filas = []
    if base.exists():
        for d in sorted(p for p in base.iterdir() if p.is_dir() and (p / "metadata.json").exists()):
            try:
                m = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            filas.append({
                "run_id": m.get("run_id", d.name),
                "fecha_hora": m.get("fecha_hora"),
                "fecha_datos": m.get("fecha_datos"),
                "horizonte": m.get("config", {}).get("horizonte"),
                "n_activos": len(m.get("activos_analizados", [])),
                "portafolios": ", ".join(m.get("portafolios", [])),
                "ruta": str(d),
            })
    return pd.DataFrame(filas, columns=["run_id", "fecha_hora", "fecha_datos", "horizonte", "n_activos",
                                        "portafolios", "ruta"])


def cargar_corrida(ruta: str | Path) -> dict:
    """Lee una corrida guardada: dict con metadata, senales, pesos (dict portafolio -> Serie), resumen,
    asignacion y precios."""
    d = Path(ruta)
    meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
    senales = pd.read_csv(d / "senales.csv", index_col=0, encoding="utf-8")
    largo = pd.read_csv(d / "pesos.csv", encoding="utf-8")
    pesos = {k: g.set_index("activo")["peso"] for k, g in largo.groupby("portafolio", sort=False)}
    resumen = pd.read_csv(d / "resumen_portafolios.csv", index_col=0, encoding="utf-8")
    asign = pd.read_csv(d / "asignacion.csv", encoding="utf-8") if (d / "asignacion.csv").exists() else None
    precios = pd.read_csv(d / "precios.csv", index_col=0, encoding="utf-8")["precio"]
    return {"metadata": meta, "senales": senales, "pesos": pesos, "resumen": resumen, "asignacion": asign,
            "precios": precios, "ruta": str(d)}
