import numpy as np
import pandas as pd

from src import riesgo as R


def test_retornos_semanales(precios):
    rs = R.retornos(precios[["A", "B"]], "W")
    rd = R.retornos(precios[["A", "B"]], "D")
    assert len(rs) < len(rd) / 4
    assert rs.index.dayofweek.unique().tolist() == [4]  # viernes


def test_ventana_excluye_jovenes_y_recorta(precios):
    p, exc = R.seleccionar_ventana(precios, 3.0, 0.9)
    assert "JOVEN" in exc and "JOVEN" not in p.columns
    assert p.notna().all().all()
    p2, exc2 = R.seleccionar_ventana(precios, 3.0, 0.3, recortar=False)
    assert "JOVEN" in p2.columns  # ~40% de cobertura (1,2 de los 3 años)
    assert R.recortar_inicio_comun(p2).index.min() == precios["JOVEN"].first_valid_index()


def test_gemelos(precios):
    p, _ = R.seleccionar_ventana(precios, 3.0, 0.9)
    g = R.grupos_gemelos(R.retornos(p, "W"), 0.99, 1.25, historia=p.notna().sum(), preferencia=list(p.columns))
    assert ["A", "GEMELO_A"] in g
    assert not any("APALANCADO" in grupo for grupo in g)  # correlación 1 pero el doble de volatilidad


def test_covarianza_psd(precios):
    r = R.retornos(precios[["A", "B", "C", "D", "BONO"]].iloc[-800:], "W")
    cov, s = R.covarianza(r, 52)
    assert np.allclose(cov.to_numpy(), cov.to_numpy().T)
    assert np.linalg.eigvalsh(cov.to_numpy()).min() > 0
    assert 0 <= s <= 1
    assert 0.05 < np.sqrt(cov.at["A", "A"]) < 0.6  # volatilidad anual razonable


def test_retornos_esperados(precios):
    r = R.retornos(precios[["BENCH", "A", "APALANCADO"]].iloc[-800:], "W")
    mu_h = R.retornos_esperados(r, "historico", 52, 0.03)
    total = (1 + r["A"]).prod() ** (52 / len(r)) - 1
    assert abs(mu_h["A"] - total) < 1e-12
    mu_c = R.retornos_esperados(r, "capm", 52, 0.03, r["BENCH"])
    # beta semanal de un 2x diario: casi 2 (no exacto por la capitalización dentro de la semana)
    assert abs((mu_c["APALANCADO"] - 0.03) / (mu_c["BENCH"] - 0.03) - 2.0) < 0.05


def test_black_litterman(cov_simple):
    score = pd.Series({"W": 90.0, "X": 50.0, "Y": 50.0, "Z": 10.0})
    post, previa, vistas = R.black_litterman(cov_simple, 0.03, 2.5, score, 0.05, 0.25)
    dif = post - previa
    assert dif["W"] > 0 and dif["Z"] < 0
    assert set(vistas.index) == set(score.index)
    p2, prev2, v2 = R.black_litterman(cov_simple, 0.03, 2.5, pd.Series(dtype=float))
    pd.testing.assert_series_equal(p2, prev2)
    assert v2.empty


def test_aversion_riesgo():
    rng = np.random.default_rng(0)
    assert R.aversion_riesgo(pd.Series(rng.normal(-0.01, 0.02, 200)), 0.03, 52) == 2.5  # rindió menos que rf
    d = R.aversion_riesgo(pd.Series(rng.normal(0.003, 0.02, 200)), 0.0, 52)
    assert 1.0 <= d <= 6.0
