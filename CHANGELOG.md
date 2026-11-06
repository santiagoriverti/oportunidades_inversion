# Changelog

## 0.1.0 — 2026-11-06

Primera versión completa.

- Universo por defecto (`data/universo.csv`): 87 tickers de la lista original, 81 analizados, con correcciones
  documentadas.
- Datos de Yahoo Finance en USD (conversión de EUR, días hábiles, inicio válido para historia de SPACs),
  tasa libre de riesgo `^IRX`, calidad de datos.
- Score de oportunidad (técnico, estadístico y fundamental por percentiles), señales absolutas, alertas
  (cuchillo que cae, trampa de valor) y clasificación; media vida de reversión y Hurst.
- Fundamentales de Yahoo con P/E relativo al ETF del sector y corrección de ADRs con monedas mezcladas.
- Métricas de riesgo por activo (Sharpe, Sortino, Calmar, VaR/CVaR, beta, alfa).
- 8 portafolios (1/N, mínima varianza, máximo Sharpe, volatilidad objetivo, paridad de riesgo, HRP,
  Black-Litterman con señales, oportunidades) con covarianza semanal Ledoit-Wolf, gemelos y frontera eficiente.
- Qué comprar en EE.UU. y en CEDEARs (data912, MEP implícito, equivalentes).
- Backtest walk-forward con costos e IC del score.
- Registro de corridas en Google Drive y seguimiento ex-post con ranking de estrategias.
- Notebooks 01 y 02 para Colab (generados por `scripts/gen_notebooks.py`), Excel + reporte HTML + ZIP.
- 57 tests con datos sintéticos y CI en GitHub Actions (Python 3.12).
