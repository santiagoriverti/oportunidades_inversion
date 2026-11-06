import pandas as pd

from src import backtest as B
from src.estrategias import armar_portafolios
from src.portafolios import NOMBRES

CANDS = ["BENCH", "A", "B", "C", "D", "E", "BONO", "GEMELO_A", "APALANCADO", "JOVEN"]


def test_fechas_rebalanceo(precios):
    f = B.fechas_rebalanceo(precios.index, "2021-01-01", "Q")
    assert all(x.month in (3, 6, 9, 12) for x in f)
    assert f[-1] < precios.index.max()
    assert len(B.fechas_rebalanceo(precios.index, "2021-01-01", "M")) > 3 * len(f) - 3


def test_armar_portafolios(precios, cfg):
    score = pd.Series({c: 50.0 for c in CANDS})
    score["C"] = 95.0
    res = armar_portafolios(precios, CANDS, cfg, 0.03, score=score, top=["C", "E", "GEMELO_A"],
                            benchmark="BENCH", preferencia=CANDS)
    assert "JOVEN" in res["excluidos"]
    assert res["excluidos"]["GEMELO_A"].startswith("gemelo de A")
    for k in NOMBRES:
        w = res["pesos"][k]
        assert w is not None, k
        assert abs(w.sum() - 1) < 1e-8 and (w >= 0).all()
        assert w.max() <= max(cfg.peso_maximo, 1 / len(w)) + 1e-6
    # el gemelo excluido que estaba en el top se reemplaza por su representante
    assert "A" in res["pesos"]["oportunidades"].index


def test_sin_mirar_el_futuro(precios, cfg):
    """Los pesos a una fecha no cambian si se alteran los precios posteriores."""
    t = precios.index[1200]
    futuro = precios.copy()
    futuro.loc[futuro.index > t] *= 3.0
    a = armar_portafolios(precios, CANDS, cfg, 0.03, fecha=t, benchmark="BENCH")
    b = armar_portafolios(futuro, CANDS, cfg, 0.03, fecha=t, benchmark="BENCH")
    for k in ("minima_varianza", "maximo_sharpe", "paridad_riesgo", "hrp"):
        pd.testing.assert_series_equal(a["pesos"][k], b["pesos"][k])


def test_backtest_corre_y_costos_restan(precios, cfg):
    cfg.ventana_anios = 2.0
    cfg.rebalanceo = "S"
    r0 = B.correr_backtest(precios, CANDS, cfg, 0.03, "BENCH", mostrar_progreso=False)
    assert {"pesos_iguales", "maximo_sharpe", "BENCH"} <= set(r0["retornos"].columns)
    assert not r0["ic"].empty and "ic_spearman" in r0["ic"].columns
    cfg.costo_bps = 200.0
    r1 = B.correr_backtest(precios, CANDS, cfg, 0.03, "BENCH", mostrar_progreso=False)
    assert r1["metricas"].loc[NOMBRES["maximo_sharpe"], "retorno_total"] < \
        r0["metricas"].loc[NOMBRES["maximo_sharpe"], "retorno_total"]
    res = B.resumen_ic(r0["ic"])
    assert set(res) >= {"ic_medio", "pct_ic_positivo"}
