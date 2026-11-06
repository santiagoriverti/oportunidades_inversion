import numpy as np
import pandas as pd

from src import portafolios as P


def _vol(w, cov):
    w = w.reindex(cov.index).fillna(0).to_numpy()
    return float(np.sqrt(w @ cov.to_numpy() @ w))


def _valido(w, tope=1.0):
    assert abs(w.sum() - 1) < 1e-8
    assert (w >= -1e-10).all()
    assert w.max() <= tope + 1e-6


MU = pd.Series({"W": 0.12, "X": 0.10, "Y": 0.07, "Z": 0.04})


def test_limpiar_pesos():
    w = P.limpiar_pesos(pd.Series({"a": 0.6, "b": 0.3, "c": 0.09, "d": 0.01}), minimo=0.02, maximo=0.5)
    _valido(w, 0.5)
    assert w["d"] == 0.0
    w2 = P.limpiar_pesos(pd.Series({"a": 1.0, "b": 1.0}), maximo=0.2)  # tope infactible -> 1/n
    assert np.allclose(w2.to_numpy(), 0.5)


def test_minima_varianza(cov_simple):
    w = P.minima_varianza(cov_simple, 0.6)
    _valido(w, 0.6)
    assert _vol(w, cov_simple) <= _vol(P.pesos_iguales(list(cov_simple.index)), cov_simple) + 1e-12


def test_maximo_sharpe_es_el_mejor(cov_simple):
    rf = 0.02
    w, nota = P.maximo_sharpe(MU, cov_simple, rf, 0.6)
    _valido(w, 0.6)

    def sh(x):
        return (float(x.reindex(MU.index).fillna(0) @ MU) - rf) / _vol(x, cov_simple)

    rng = np.random.default_rng(0)
    for _ in range(300):
        x = pd.Series(rng.dirichlet(np.ones(4)), index=MU.index)
        if x.max() <= 0.6:
            assert sh(w) >= sh(x) - 1e-6
    assert sh(w) >= sh(P.minima_varianza(cov_simple, 0.6)) - 1e-9


def test_maximo_sharpe_sin_exceso(cov_simple):
    w, nota = P.maximo_sharpe(MU * 0 + 0.01, cov_simple, 0.05, 1.0)
    assert "mínima varianza" in nota
    _valido(w)


def test_volatilidad_objetivo(cov_simple):
    w, nota = P.volatilidad_objetivo(MU, cov_simple, 0.10, 0.6)
    _valido(w, 0.6)
    assert _vol(w, cov_simple) <= 0.10 + 1e-6
    w2, nota2 = P.volatilidad_objetivo(MU, cov_simple, 0.001, 0.6)
    assert "menor que la mínima" in nota2


def test_paridad_riesgo(cov_simple):
    w = P.paridad_riesgo(cov_simple)
    _valido(w)
    rc = P.contribuciones_riesgo(w, cov_simple)
    assert np.allclose(rc.to_numpy(), 0.25, atol=1e-4)


def test_hrp(cov_simple):
    w = P.hrp(cov_simple)
    _valido(w)
    assert w["Z"] == w.max()  # el de menor volatilidad pesa más


def test_frontera(cov_simple):
    f = P.frontera_eficiente(MU, cov_simple, 0.6, puntos=12)
    assert len(f) >= 10
    assert (f["volatilidad"].diff().dropna() >= -1e-6).all()
    assert (f["retorno"].diff().dropna() >= -1e-9).all()


def test_resumen(cov_simple):
    pesos = {"pesos_iguales": P.pesos_iguales(list(cov_simple.index)), "hrp": P.hrp(cov_simple)}
    t = P.resumen(pesos, MU, cov_simple, 0.02)
    assert list(t["clave"]) == ["pesos_iguales", "hrp"]
    assert (t["n_efectivo"] <= 4 + 1e-9).all()
