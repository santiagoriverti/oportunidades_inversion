"""Datos sintéticos para los tests (sin red): precios con un factor de mercado común, un gemelo casi idéntico,
un ETF apalancado 2x, un bono de baja volatilidad y un activo joven."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config import Config


def _panel(semilla: int = 42, anios: int = 6) -> pd.DataFrame:
    idx = pd.bdate_range("2018-01-01", periods=252 * anios)
    rng = np.random.default_rng(semilla)
    n = len(idx)
    f = rng.normal(0.0003, 0.01, n)  # factor de mercado
    especs = {  # beta, alfa diario, desvío idiosincrático
        "BENCH": (1.0, 0.0, 0.0),
        "A": (1.2, 0.0002, 0.012),
        "B": (0.8, 0.0001, 0.010),
        "C": (0.3, 0.0002, 0.006),
        "D": (1.0, -0.0002, 0.020),
        "E": (0.5, 0.0003, 0.015),
        "BONO": (-0.1, 0.0001, 0.003),
    }
    r = {k: a + b * f + rng.normal(0, s, n) for k, (b, a, s) in especs.items()}
    r["GEMELO_A"] = r["A"] + rng.normal(0, 0.0005, n)
    r["APALANCADO"] = 2.0 * r["BENCH"]
    p = pd.DataFrame({k: 100.0 * np.exp(np.cumsum(v)) for k, v in r.items()}, index=idx)
    joven = p["E"].copy() * 0.5
    joven.iloc[: int(n * 0.8)] = np.nan
    p["JOVEN"] = joven
    return p


@pytest.fixture(scope="session")
def precios() -> pd.DataFrame:
    return _panel()


@pytest.fixture()
def cfg() -> Config:
    return Config.desde_horizonte("mediano", tickers=["A", "B"], incluir_fundamentales=False,
                                  correr_backtest=False, guardar_registro=False)


@pytest.fixture(scope="session")
def cov_simple() -> pd.DataFrame:
    """Covarianza anual chica y conocida (4 activos)."""
    vol = np.array([0.20, 0.15, 0.10, 0.05])
    corr = np.array([[1.0, 0.6, 0.3, 0.0],
                     [0.6, 1.0, 0.4, 0.1],
                     [0.3, 0.4, 1.0, 0.2],
                     [0.0, 0.1, 0.2, 1.0]])
    idx = ["W", "X", "Y", "Z"]
    return pd.DataFrame(np.outer(vol, vol) * corr, index=idx, columns=idx)
