import numpy as np
import pandas as pd

from src import asignacion as A

PESOS = pd.Series({"SPY": 0.5, "GLD": 0.3, "BTC-USD": 0.2})
PRECIOS = pd.Series({"SPY": 700.0, "GLD": 370.0, "BTC-USD": 75000.0})


def test_discreta_no_gasta_de_mas():
    t, sobrante = A.asignacion_discreta(PESOS, PRECIOS, 10_000)
    assert (t["cantidad"] == np.floor(t["cantidad"])).all()
    assert t["monto"].sum() + sobrante <= 10_000 + 1e-6
    assert t.at["BTC-USD", "cantidad"] == 0 and t.at["BTC-USD", "nota"] == "no alcanza para 1 unidad"


def test_fraccionables_y_fracciones():
    t, s = A.asignacion_discreta(PESOS, PRECIOS, 10_000, fraccionables={"BTC-USD"})
    assert 0 < t.at["BTC-USD", "cantidad"] < 1
    t2, s2 = A.asignacion_discreta(PESOS, PRECIOS, 10_000, fracciones=True)
    assert abs(t2["monto"].sum() + s2 - 10_000) < 1e-6
    assert s2 < 10.0  # con 4 decimales sobra a lo sumo 0,0001 unidad de cada activo (BTC: USD 7,5)


def test_sin_precio():
    t, s = A.asignacion_discreta(pd.Series({"X": 1.0}), pd.Series({"X": np.nan}), 1000)
    assert t.at["X", "nota"] == "sin precio" and s == 1000


def test_precios_y_asignacion_cedears():
    cot = pd.DataFrame({"c": [13.0, 20000.0, 8000.0], "v": [1e5, 1e5, 1e5]}, index=["SPYD", "SPY", "GOOGL"])
    t = A.precios_cedears({"SPY": "SPY", "GOOG": "GOOGL", "CLX": "CLX"}, cot, mep=1600.0)
    assert t.at["SPY", "especie"] == "SPYD" and t.at["SPY", "precio_usd"] == 13.0
    assert abs(t.at["GOOG", "precio_usd"] - 5.0) < 1e-9
    assert "CLX" not in t.index
    tabla, s = A.asignacion_con_cedears(pd.Series({"SPY": 0.6, "CLX": 0.4}), pd.Series({"SPY": 700.0, "CLX": 100.0}),
                                        t, 10_000)
    assert tabla.at["SPY", "vehiculo"] == "CEDEAR SPYD"
    assert tabla.at["CLX", "vehiculo"].startswith("sin CEDEAR")
    assert tabla["monto"].sum() + s <= 10_000 + 1e-6


def test_con_equivalentes():
    t = pd.DataFrame({"especie": ["IBITD"], "precio_usd": [4.5], "fuente": ["especie D (dólar MEP)"],
                      "volumen": [1.0]}, index=["IBIT"])
    t2 = A.con_equivalentes(t, [["BTC-USD", "IBIT"]])
    assert t2.at["BTC-USD", "especie"] == "IBITD"
    assert "equivalente" in t2.at["BTC-USD", "fuente"]
