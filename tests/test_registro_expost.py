import numpy as np
import pandas as pd

from src import expost, registro


def _guardar(tmp_path, precios, fecha):
    senales = pd.DataFrame({"score": [80.0, 40.0, 60.0], "clasificacion": ["Oportunidad", "Neutral", "Vigilar"]},
                           index=["A", "B", "C"])
    pesos = {"pesos_iguales": pd.Series({"A": 0.5, "B": 0.5}), "hrp": pd.Series({"C": 1.0})}
    resumen = pd.DataFrame({"clave": ["pesos_iguales", "hrp"], "sharpe": [1.0, 0.5]},
                           index=["Pesos iguales (1/N)", "HRP (López de Prado)"])
    meta = {"fecha_datos": str(fecha.date()), "benchmark": "BENCH", "config": {"plazos_expost": [21, 63]},
            "activos_analizados": ["A", "B", "C"], "portafolios": list(pesos), "monedas": {}}
    return registro.guardar_corrida(tmp_path, meta, senales, pesos, resumen, None, precios.loc[fecha, ["A", "B", "C"]])


def test_guardar_y_cargar(tmp_path, precios):
    fecha = precios.index[-200]
    d = _guardar(tmp_path, precios, fecha)
    c = registro.cargar_corrida(d)
    assert c["metadata"]["run_id"] == d.name
    assert abs(c["pesos"]["pesos_iguales"].sum() - 1) < 1e-12
    assert c["senales"].loc["A", "clasificacion"] == "Oportunidad"
    lista = registro.listar_corridas(tmp_path)
    assert len(lista) == 1 and lista.iloc[0]["fecha_datos"] == str(fecha.date())
    d2 = _guardar(tmp_path, precios, fecha)  # misma hora: no pisa la anterior
    assert d2 != d and len(registro.listar_corridas(tmp_path)) == 2


def test_evaluar_corrida(tmp_path, precios):
    fecha = precios.index[-200]
    c = registro.cargar_corrida(_guardar(tmp_path, precios, fecha))
    e = expost.evaluar_corrida(c, precios, "BENCH", 0.03)
    rel = precios.iloc[-1] / precios.loc[fecha]
    esperado = 0.5 * rel["A"] + 0.5 * rel["B"] - 1
    assert abs(e["tabla"].loc["Pesos iguales (1/N)", "retorno_total"] - esperado) < 1e-10
    assert abs(e["tabla"].loc["Benchmark (BENCH)", "retorno_total"] - (rel["BENCH"] - 1)) < 1e-10
    assert e["dias"] == 199
    assert np.isfinite(e["tabla"].loc["HRP (López de Prado)", "sharpe"])  # 199 días >= 63
    assert abs(e["tabla"].loc["HRP (López de Prado)", "ret_21d"] -
               (precios["C"].loc[fecha:].iloc[21] / precios.at[fecha, "C"] - 1)) < 1e-10
    todas = expost.evaluar_todas([c], precios, "BENCH", 0.03)
    assert set(todas["ranking"].index) == {"Pesos iguales (1/N)", "HRP (López de Prado)"}
