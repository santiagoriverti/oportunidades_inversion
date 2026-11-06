"""Oportunidades de inversión: activos artificialmente bajos, portafolios óptimos y seguimiento ex-post.

Módulos (ver docs/ARQUITECTURA.md):
    config        parámetros del análisis (perfiles por horizonte)
    universo      lista de tickers, símbolos de Yahoo, monedas, CEDEARs
    datos         descarga de precios (yfinance), conversión a USD, calidad, tasa libre de riesgo, CEDEARs
    fundamentales valuación de acciones (P/E, PEG, FCF yield, upside de analistas, P/E vs sector)
    indicadores   indicadores técnicos y estadísticos (paneles en el tiempo y foto a una fecha)
    senales       score de oportunidad, señales absolutas, alertas y clasificación
    metricas      métricas de riesgo y performance (Sharpe, Sortino, drawdown, VaR, beta...)
    riesgo        retornos, ventana, gemelos, covarianza Ledoit-Wolf, retornos esperados, Black-Litterman
    portafolios   optimizadores (mínima varianza, máximo Sharpe, paridad de riesgo, HRP...) y frontera
    estrategias   arma todos los portafolios a una fecha (lo usan el análisis y el backtest)
    asignacion    cuántas acciones/ETFs o CEDEARs comprar con un capital
    backtest      backtest walk-forward de todas las estrategias
    registro      guarda y lee corridas (Google Drive o carpeta local)
    expost        performance real de las corridas guardadas
    graficos      gráficos interactivos (plotly)
    tablas        tablas con formato para los notebooks
    exportar      Excel, reporte HTML y ZIP
    pipeline      clase Analisis que orquesta todo
"""
__version__ = "0.1.0"
