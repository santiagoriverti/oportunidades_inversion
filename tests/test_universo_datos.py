import numpy as np
import pandas as pd
import pytest

from src import datos, fundamentales, universo as U
from src.config import Config


def test_universo_por_defecto():
    u = U.cargar_universo()
    assert len(u) == 87
    assert u["estado"].value_counts().to_dict() == {"activo": 81, "excluido": 5, "referencia": 1}
    fila = u.set_index("ticker")
    assert fila.at["BRKB", "yahoo"] == "BRK-B" and fila.at["VGII", "yahoo"] == "VGIT"
    assert fila.at["OKLO", "inicio_valido"] == "2024-05-10"
    assert set(u.loc[u["estado"] == "excluido", "ticker"]) == {"AO28", "HJCLO", "NPCDO", "YMCXO", "UN"}


def test_resolver_lista_propia():
    u = U.resolver_universo([" brkb", "BTC", "btc-usd", "aapl", "IXIC", "SAP.DE", ""])
    assert u["yahoo"].tolist() == ["BRK-B", "BTC-USD", "AAPL", "^IXIC", "SAP.DE"]
    assert u.set_index("yahoo").at["^IXIC", "estado"] == "referencia"
    assert u.set_index("yahoo").at["SAP.DE", "moneda"] == "EUR"
    with pytest.raises(ValueError):
        U.resolver_universo(["", " "])


def test_monedas_y_cedears():
    assert U.moneda_por_sufijo("EXX1.DE") == "EUR" and U.moneda_por_sufijo("SPY") == "USD"
    assert U.moneda_por_sufijo("IUIT.L") is None
    assert U.cedear_por_defecto("BRK-B") == "BRKB" and U.cedear_por_defecto("BTC-USD") == ""
    m = U.mapa_cedears(U.cargar_universo())
    assert m["GOOG"] == "GOOGL" and m["SPY"] == "SPY" and m["EXX1.DE"] == ""


def test_config():
    c = Config.desde_horizonte("largo")
    assert c.ventana_anios == 5.0 and c.rebalanceo == "S"
    with pytest.raises(ValueError):
        Config.desde_horizonte("mediano", peso_maximo=1.5)
    with pytest.raises(ValueError):
        Config.desde_horizonte("eterno")
    assert Config.desde_dict({**c.como_dict(), "clave_vieja": 1}).horizonte == "largo"


def test_extraer_y_alinear():
    idx = pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-05", "2026-01-07"])  # vie, sáb, lun, mié
    cols = pd.MultiIndex.from_product([["Close", "Open"], ["AAA", "BBB"]], names=["Price", "Ticker"])
    df = pd.DataFrame(np.arange(16, dtype=float).reshape(4, 4), index=idx, columns=cols)
    c = datos._extraer_cierres(df, ["AAA", "BBB"])
    assert list(c.columns) == ["AAA", "BBB"] and c.iloc[0, 0] == 0.0
    simple = datos._extraer_cierres(df["Close"].rename(columns={"AAA": "Close"})[["Close"]], ["ZZZ"])
    assert list(simple.columns) == ["ZZZ"]
    a = datos.alinear_dias_habiles(c)
    assert pd.Timestamp("2026-01-03") not in a.index           # sábado fuera
    assert a.at[pd.Timestamp("2026-01-06"), "AAA"] == c.at[pd.Timestamp("2026-01-05"), "AAA"]  # feriado completado


def test_convertir_a_usd_y_calidad():
    idx = pd.bdate_range("2026-01-01", periods=10)
    p = pd.DataFrame({"X.DE": 10.0, "Y": 5.0}, index=idx)
    fx = pd.DataFrame({"EURUSD=X": 1.1}, index=idx)
    out, avisos = datos.convertir_a_usd(p, {"X.DE": "EUR", "Y": "USD"}, idx[0], fx=fx)
    assert np.allclose(out["X.DE"], 11.0) and np.allclose(out["Y"], 5.0) and not avisos
    q = datos.reporte_calidad(p.iloc[:7], p, idx[0], idx[-1])
    assert q.at["Y", "dias_sin_dato"] == 3


def test_tabla_fundamentales():
    info = {
        "AAA": {"quoteType": "EQUITY", "currency": "USD", "financialCurrency": "USD", "sector": "Technology",
                "trailingPE": 20.0, "forwardPE": 16.0, "trailingPegRatio": 0.8, "marketCap": 1e9,
                "freeCashflow": 5e7, "dividendRate": 1.0, "currentPrice": 50.0, "targetMeanPrice": 60.0,
                "numberOfAnalystOpinions": 10},
        "VALE": {"quoteType": "EQUITY", "currency": "USD", "financialCurrency": "BRL", "sector": "Basic Materials",
                 "trailingPE": 72.0, "forwardPE": 6.0, "trailingAnnualDividendYield": 0.49, "dividendRate": 0.84,
                 "currentPrice": 11.5, "targetMeanPrice": 15.0, "numberOfAnalystOpinions": 2},
        "SPY": {"quoteType": "ETF", "trailingPE": 23.0, "netExpenseRatio": 0.0945, "yield": 0.011},
    }
    t = fundamentales.tabla_fundamentales(info, {"XLK": {"trailingPE": 25.0}})
    assert abs(t.at["AAA", "upside_analistas"] - 0.2) < 1e-12
    assert abs(t.at["AAA", "pe_relativo_sector"] - 0.8) < 1e-12
    assert abs(t.at["AAA", "fcf_yield"] - 0.05) < 1e-12 and abs(t.at["AAA", "rend_dividendo"] - 0.02) < 1e-12
    assert bool(t.at["VALE", "monedas_mezcladas"]) and np.isnan(t.at["VALE", "pe_trailing"])
    assert abs(t.at["VALE", "rend_dividendo"] - 0.84 / 11.5) < 1e-12   # no el 49% mezclado
    assert np.isnan(t.at["VALE", "upside_analistas"])                  # menos de 3 analistas
    assert abs(t.at["SPY", "gasto_anual_etf"] - 0.000945) < 1e-12
    assert np.isnan(t.at["SPY", "peg"])
