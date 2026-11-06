import numpy as np
import pandas as pd

from src import metricas as M


def test_cagr_y_volatilidad():
    r = pd.Series(np.full(252, 0.001))
    assert abs(M.cagr(r) - (1.001 ** 252 - 1)) < 1e-12
    assert M.volatilidad(r) < 1e-12
    assert np.isnan(M.sharpe(r))  # desvío cero


def test_max_drawdown_y_calmar():
    r = pd.Series([0.2, -0.5, 0.5])  # 1 -> 1,2 -> 0,6 -> 0,9
    assert abs(M.max_drawdown(r) - (-0.5)) < 1e-12
    assert M.calmar(r) < 0  # CAGR negativo (terminó en 0,9) sobre una caída de 50%


def test_var_cvar_normal():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0, 0.01, 200_000))
    assert abs(M.var_historico(r) - 0.01645) < 0.0005
    assert M.cvar_historico(r) > M.var_historico(r)


def test_sharpe_sortino_signo():
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0.001, 0.01, 1000))
    assert M.sharpe(r, 0.0) > 0
    assert M.sortino(r, 0.0) > M.sharpe(r, 0.0)  # la desviación a la baja es menor que el desvío total


def test_beta_alfa():
    rng = np.random.default_rng(2)
    m = pd.Series(rng.normal(0.002, 0.02, 500))
    r = 2.0 * m + rng.normal(0, 0.002, 500)
    beta, alfa, corr = M.beta_alfa(r, m, 0.0, 52)
    assert abs(beta - 2.0) < 0.05
    assert corr > 0.99


def test_tabla_metricas_activos(precios):
    t = M.tabla_metricas_activos(precios, precios.index[-756], 0.03, "BENCH")
    assert {"retorno_anual", "volatilidad", "sharpe", "beta", "max_drawdown"} <= set(t.columns)
    assert abs(t.at["BENCH", "beta"] - 1.0) < 1e-9
    assert abs(t.at["APALANCADO", "beta"] - 2.0) < 0.1
