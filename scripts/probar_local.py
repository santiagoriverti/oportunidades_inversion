"""Corre el análisis completo en la PC (sin notebook), con datos reales de Yahoo.

Uso (desde la raíz del repo; en Windows con PYTHONUTF8=1):
    python scripts/probar_local.py                 # universo por defecto, todo (backtest incluido)
    python scripts/probar_local.py --rapido        # sin fundamentales ni backtest
    python scripts/probar_local.py --tickers SPY GLD NVDA BTC-USD --sin-backtest
    python scripts/probar_local.py --guardar-en data/ejemplo_registro   # corrida de ejemplo del repo

Guarda la corrida en registros_local/ (o --guardar-en) y el ZIP en _descargas/ (ignorados por git).
"""
from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402

from src.config import Config  # noqa: E402
from src.pipeline import Analisis  # noqa: E402
from src.portafolios import NOMBRES  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", nargs="*", default=None)
    ap.add_argument("--horizonte", default="mediano", choices=["corto", "mediano", "largo"])
    ap.add_argument("--rapido", action="store_true", help="sin fundamentales ni backtest")
    ap.add_argument("--sin-backtest", action="store_true")
    ap.add_argument("--sin-fundamentales", action="store_true")
    ap.add_argument("--guardar-en", default=None, help="carpeta del registro (por defecto registros_local/)")
    ap.add_argument("--sin-zip", action="store_true")
    a = ap.parse_args()
    warnings.filterwarnings("ignore", category=FutureWarning)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)

    cfg = Config.desde_horizonte(a.horizonte, tickers=a.tickers,
                                 incluir_fundamentales=not (a.rapido or a.sin_fundamentales),
                                 correr_backtest=not (a.rapido or a.sin_backtest),
                                 carpeta_registros=a.guardar_en)
    t0 = time.time()
    A = Analisis(cfg)
    A.cargar_datos().calcular_senales().optimizar().asignar()
    if cfg.correr_backtest:
        A.correr_backtest()
    A.guardar()

    print("\n=== Top 15 por score ===")
    cols = ["nombre", "clasificacion", "score", "n_senales", "ret_3m", "dist_sma200", "zscore_1a", "rsi_14",
            "upside_analistas", "alertas"]
    print(A.senales[[c for c in cols if c in A.senales.columns]].head(15).round(3).to_string())
    print("\n=== Clasificación ===")
    print(A.senales["clasificacion"].value_counts().to_string())
    print("\n=== Portafolios (ex-ante e histórico en la ventana) ===")
    print(A.resumen.drop(columns=["clave"]).round(3).to_string())
    print("\n=== Gemelos ===")
    print(A.tabla_gemelos.to_string(index=False))
    print("\n=== Excluidos de la optimización ===")
    print(A.excluidos_opt.to_string())
    k = "maximo_sharpe"
    t, s = A.tabla_compra(k, "usd")
    print(f"\n=== Qué comprar: {NOMBRES[k]} (EE.UU.), sobrante USD {s:,.2f} ===")
    print(t.round(4).to_string())
    if "cedear" in A.asignaciones[k]:
        t, s = A.tabla_compra(k, "cedear")
        print(f"\n=== Qué comprar: {NOMBRES[k]} (CEDEARs), sobrante USD {s:,.2f} ===")
        print(t.round(4).to_string())
    if A.backtest is not None:
        print("\n=== Backtest ===")
        print(A.backtest["metricas"].round(3).to_string())
        print("\nIC del score:", {k_: round(v, 3) for k_, v in A.resumen_ic.items()})
    if A.avisos:
        print("\n=== Avisos ===")
        for x in A.avisos:
            print(" -", x)
    if not a.sin_zip:
        A.exportar(descargar=False)
    print(f"\nTotal: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
