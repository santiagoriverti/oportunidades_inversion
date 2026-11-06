import numpy as np
import pandas as pd

from src import senales as S
from src.config import UMBRALES_SENALES

PESOS = {"tecnico": 0.4, "estadistico": 0.3, "fundamental": 0.3}


def _foto(n=20, semilla=0):
    rng = np.random.default_rng(semilla)
    idx = [f"T{i:02d}" for i in range(n)]
    f = pd.DataFrame({
        "dist_sma50": rng.normal(0, 0.05, n), "dist_sma200": rng.normal(0, 0.1, n),
        "posicion_52s": rng.uniform(0.2, 0.9, n), "rsi_14": rng.uniform(40, 65, n),
        "bollinger_pctb": rng.uniform(0.2, 0.9, n), "zscore_1a": rng.normal(0, 0.8, n),
        "z_tendencia_3a": rng.normal(0, 0.8, n), "z_ret_3m": rng.normal(0, 0.8, n),
        "z_relativo_bench": rng.normal(0, 0.8, n), "ret_1m": rng.normal(0, 0.03, n),
        "tendencia_alcista": 1.0, "dias_historia": 2000.0, "drawdown_52s": rng.uniform(-0.2, 0, n),
    }, index=idx)
    # T00: barato en todo; T01: caro en todo
    f.loc["T00"] = [-0.15, -0.30, 0.02, 22, -0.2, -2.5, -2.2, -2.0, -2.1, -0.05, 1.0, 2000.0, -0.35]
    f.loc["T01"] = [0.15, 0.30, 0.99, 80, 1.1, 2.5, 2.2, 2.0, 2.1, 0.08, 1.0, 2000.0, 0.0]
    return f


def test_percentil():
    p = S.percentil(pd.Series([1.0, 2.0, 3.0, np.nan]), -1)
    assert p.iloc[0] > p.iloc[1] > p.iloc[2]
    assert np.isnan(p.iloc[3])
    assert 0 < p.min() and p.max() < 1


def test_score_ordena_y_clasifica():
    t = S.calcular_score(_foto(), None, PESOS, UMBRALES_SENALES)
    assert t.index[0] == "T00"
    assert t.at["T00", "clasificacion"] == "Oportunidad"
    assert t.at["T00", "n_senales"] >= 5
    assert t.at["T01", "clasificacion"] == "Sobreextendida"
    assert t["score"].between(0, 100).all()
    assert t.at["T00", "score_fundamental"] != t.at["T00", "score_fundamental"]  # NaN: sin fundamentales


def test_fundamentales_entran_y_alertas():
    f = _foto()
    fund = pd.DataFrame({"upside_analistas": 0.0, "pe_relativo_sector": 1.0, "peg": 2.0, "fcf_yield": 0.03,
                         "crec_implicito": 0.1}, index=f.index)
    fund.loc["T00", ["upside_analistas", "pe_relativo_sector", "peg", "fcf_yield", "crec_implicito"]] = [0.4, 0.6, 0.8, 0.08, -0.2]
    t = S.calcular_score(f, fund, PESOS, UMBRALES_SENALES)
    assert t.at["T00", "score_fundamental"] > 90
    assert "trampa de valor" in t.at["T00", "alertas"]
    assert t.at["T00", "clasificacion"] == "Oportunidad con alertas"


def test_cuchillo_y_sin_datos():
    f = _foto()
    f.loc["T00", ["ret_1m", "tendencia_alcista"]] = [-0.25, 0.0]
    f.loc["T05", ["dist_sma50", "dist_sma200", "posicion_52s", "rsi_14", "bollinger_pctb", "zscore_1a",
                  "z_tendencia_3a", "z_ret_3m", "z_relativo_bench"]] = np.nan
    t = S.calcular_score(f, None, PESOS, UMBRALES_SENALES)
    assert "cuchillo" in t.at["T00", "alertas"]
    assert t.at["T05", "clasificacion"] == "Sin datos suficientes"
    assert np.isnan(t.at["T05", "ranking"])


def test_top_oportunidades():
    t = S.calcular_score(_foto(), None, PESOS, UMBRALES_SENALES)
    top = S.top_oportunidades(t, 3)
    assert top[0] == "T00" and len(top) <= 3
