import numpy as np
import pandas as pd

from src import indicadores as I


def _serie(valores):
    return pd.Series(valores, index=pd.bdate_range("2020-01-01", periods=len(valores)), dtype=float)


def test_rsi_extremos():
    assert I.rsi(_serie(np.arange(1, 60)), 14).iloc[-1] == 100.0
    assert I.rsi(_serie(np.arange(60, 1, -1)), 14).iloc[-1] == 0.0
    assert np.isnan(I.rsi(_serie(np.full(60, 5.0)), 14).iloc[-1])


def test_distancias_y_rango():
    s = _serie(np.full(300, 10.0))
    assert abs(I.distancia_sma(s, 200).iloc[-1]) < 1e-12
    sube = _serie(np.linspace(1, 2, 300))
    assert I.posicion_rango(sube, 252).iloc[-1] == 1.0
    assert I.drawdown_rolling(sube, 252).iloc[-1] == 0.0
    baja = _serie(np.linspace(2, 1, 300))
    assert I.posicion_rango(baja, 252).iloc[-1] == 0.0
    assert I.drawdown_rolling(baja, 252).iloc[-1] < -0.3


def test_zscore_negativo_tras_caida():
    rng = np.random.default_rng(1)
    v = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 400)))
    v[-10:] *= 0.7
    assert I.zscore_log(_serie(v), 252).iloc[-1] < -1.5


def test_z_tendencia_igual_a_polyfit(precios):
    p = precios[["A", "D"]]
    z = I.z_tendencia(p, 756)
    for fecha in [p.index[800], p.index[-1]]:
        for col in p.columns:
            y = np.log(p[col].loc[:fecha].iloc[-756:].to_numpy())
            t = np.arange(len(y), dtype=float)
            b, a = np.polyfit(t, y, 1)
            res = y - (a + b * t)
            esperado = res[-1] / np.sqrt((res ** 2).sum() / (len(y) - 2))
            assert abs(z.at[fecha, col] - esperado) < 1e-6


def test_media_vida_ar1():
    rng = np.random.default_rng(3)
    phi, n = 0.95, 5000
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = phi * e[i - 1] + rng.normal()
    hl = I.media_vida(pd.Series(e))
    teorica = -np.log(2) / np.log(phi)
    assert abs(hl - teorica) / teorica < 0.3
    assert np.isnan(I.media_vida(pd.Series(np.cumsum(np.ones(100)))))


def test_hurst():
    rng = np.random.default_rng(4)
    paseo = np.cumsum(rng.normal(size=3000))
    assert 0.4 < I.hurst(pd.Series(paseo)) < 0.6
    e = np.zeros(3000)
    for i in range(1, 3000):
        e[i] = 0.5 * e[i - 1] + rng.normal()
    assert I.hurst(pd.Series(e)) < 0.3


def test_foto_sin_mirar_el_futuro(precios):
    """La foto a una fecha t es la misma con o sin los precios posteriores a t."""
    p = precios[["BENCH", "A", "B", "JOVEN"]]
    t = p.index[1100]
    completo = I.foto(I.panel_indicadores(p, "BENCH"), t)
    truncado = I.foto(I.panel_indicadores(p.loc[:t], "BENCH"), t)
    pd.testing.assert_frame_equal(completo, truncado, check_exact=False, rtol=1e-9, atol=1e-12)


def test_foto_columnas_y_activo_joven(precios):
    f = I.foto(I.panel_indicadores(precios, "BENCH"))
    for c in ["precio", "ret_1m", "dist_sma200", "zscore_1a", "z_tendencia_3a", "rsi_14", "z_relativo_bench"]:
        assert c in f.columns
    assert np.isnan(f.at["BENCH", "z_relativo_bench"])  # el benchmark contra sí mismo no tiene desvío
    assert np.isnan(f.at["JOVEN", "z_tendencia_3a"])     # menos de 3 años de historia
    assert not np.isnan(f.at["JOVEN", "rsi_14"])


def test_reversion_media(precios):
    r = I.reversion_media(precios[["A", "JOVEN"]])
    assert {"media_vida_dias", "hurst"} <= set(r.columns)
    assert np.isfinite(r.at["A", "hurst"])
