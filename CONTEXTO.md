# CONTEXTO — objetivo, decisiones, fuentes y trampas

## 1. Objetivo (pedido del usuario, 2026-11-06)

Un notebook de Colab, abrible desde el README, donde el usuario edita una lista de tickers y obtiene:
1. qué activos están **artificialmente bajos** (por ejemplo, debajo de su promedio reciente) con las métricas de
   finanzas avanzadas que existan para eso;
2. **portafolios** que maximicen el beneficio minimizando la varianza (Markowitz, Sharpe, etc.) para poder
   comprarlos;
3. todo **registrado** para entrar después y ver, ex-post, cómo le fue a cada alternativa.

La lista original de tickers (87, con rubro y comentarios) está en `data/universo.csv` (columna
`comentario_original` para los comentarios que traía).

## 2. Decisiones

### Del usuario (preguntas del 2026-11-06)

| Tema | Decisión |
|---|---|
| Dónde se registran las corridas | **Google Drive** (`Mi unidad/oportunidades_inversion/registros`) — no robot de GitHub Actions ni Google Sheets |
| Bono AO28 y ONs HJCLO, NPCDO, YMCXO | **Excluidos por ahora**: ni Yahoo ni data912 tienen su historia; renta fija va al roadmap |
| Qué comprar | **Ambos**: acciones/ETFs de EE.UU. y CEDEARs |
| Horizonte | **Mediano (6-12 meses)**: ventana de 3 años, rebalanceo trimestral, seguimiento a 1/3/6/12 meses |

### Técnicas (de Claude, revisables)

| Decisión | Por qué |
|---|---|
| Correcciones de tickers (`nota` en el CSV): `UN` excluido, `VGII`→`VGIT`, `^IXIC` referencia, `BRKB`→`BRK-B`, `BTC`→`BTC-USD`, EXX1/QDVE/VVSM `.DE` | `UN` en Yahoo es un ETF de jul-2026 y el comentario habla de Nu Bank (ya está `NU`); `VGII` no existe; `^IXIC` es un índice no invertible |
| OKLO desde 2024-05-10, SMR desde 2022-05-03 | antes Yahoo trae el precio del SPAC (plano en ~USD 10, volatilidad 2-10%): distorsiona riesgo y señales |
| Covarianza con retornos **semanales** | asincronía horaria (BTC 24/7, Xetra cierra antes): XLK/QDVE 0,56 diaria vs 0,92 semanal |
| Ledoit-Wolf | ~70 activos y 156 semanas: la covarianza muestral es inestable |
| Gemelos = correlación ≥ 0,99 **y** volatilidad parecida | SPY/VOO/VTI, GLD/IAU... casi singulares en Markowitz; SSO (2x) correlaciona 0,9996 con SPY pero no es lo mismo |
| Sacar gemelos antes de recortar la ventana | IBIT (desde ene-2024) acortaba la ventana de todos aunque después se descartara |
| Retorno esperado = CAGR histórico (por defecto) | es el Markowitz "clásico" que pidió el usuario; se advierte que premia a los que ya subieron y se agregan portafolios robustos y Black-Litterman |
| Black-Litterman con previa de pesos iguales y vistas = score | integra los objetivos 1 y 2; no hay capitalizaciones comparables entre acciones, ETFs y cripto |
| Score por percentiles + señales absolutas | los percentiles no dependen de escalas ni de extremos; las señales absolutas evitan llamar "barato" a lo menos caro de un mercado caro |
| Fundamentales solo como foto | Yahoo gratis no da historia de múltiplos (4 años de balances con huecos) |
| P/E relativo al ETF SPDR del sector | comparar P/E entre sectores distintos sesga hacia energía y bancos |
| Volatilidad objetivo 10% | con 15% salía casi igual al máximo Sharpe (14,6%); 10% da un portafolio intermedio |
| Peso máximo 20%, mínimo 2% (solo optimizados) | portafolios comprables; los diversificados (1/N, paridad, HRP) conservan todas las posiciones |
| Cripto fraccionada en la asignación | 1 BTC ≈ USD 75.000 > capital típico |
| Optimizadores propios con scipy | evitar dependencias pesadas (PyPortfolioOpt/cvxpy) que se rompen con versiones nuevas de numpy |
| Gráficos con plotly y paleta validada (skill dataviz) | un color fijo por portafolio en todos los gráficos; tablas siempre junto a los gráficos |

## 3. Fuentes

| Fuente | Qué | Notas |
|---|---|---|
| Yahoo Finance vía `yfinance` (1.8 probada) | precios ajustados, `^IRX`, tipos de cambio, `Ticker.info` | gratis, sin API key; a veces corta pedidos (se reintenta) |
| [data912](https://data912.com) `/live/arg_cedears` | precios en vivo de CEDEARs (pesos y especies D/C) | gratis, sin key; solo cotización del día (`/historical/bonds/` solo tiene soberanos viejos) |

## 4. Resultados de referencia (corrida de ejemplo, datos al 2026-11-06)

`data/ejemplo_registro/20261106_204148/`: 81 activos analizados; 13 Oportunidad + 5 con alertas; top GRID,
AIRR, SPMO, AVGO, IEMG, EWZ, VALE, FICO, VVSM.DE, COPX. Máximo Sharpe ex-ante 37,4% / vol 13,7% (GLD, EXX1.DE,
BRK-B); backtest dic-2021 → nov-2026: Máximo Sharpe 16,2% anual, SPY 10,5%; IC del score +0,003 (t = 0,05):
**el score no predijo los retornos trimestrales** en el backtest.

## 5. Trampas conocidas

- **Unidades de Yahoo**: `dividendYield` viene en % (5,02 = 5,02%) → se usa `dividendRate/precio`;
  `netExpenseRatio` en % (0,0945 = 0,0945%) → /100; `trailingAnnualDividendYield` es fracción.
- **ADRs con balance en otra moneda** (VALE: `financialCurrency` BRL) → dividendo trailing de 49% y P/E 72:
  se descartan esas métricas (`monedas_mezcladas`).
- **Precios ajustados** cambian hacia atrás con cada dividendo: el ex-post vuelve a bajar todo y nunca compara
  con precios guardados de otro día.
- **yfinance 1.x** devuelve columnas MultiIndex (`Price`, `Ticker`) incluso con un solo ticker
  (`datos._extraer_cierres` maneja ambos formatos).
- **Fecha de los datos** = último cierre del benchmark; si se corre con el mercado abierto, el último "cierre" es
  el precio del momento.
- **Colab reutiliza sesiones**: la celda SETUP hace `git fetch` + `reset --hard` y purga `src.*`; además
  actualiza yfinance (Yahoo cambia seguido y la versión vieja de Colab puede fallar).
- **pandas**: no usar los alias `"ME"`/`"QE"` (solo existen desde 2.2); agrupar por período.
- **Volatilidad ~0** por punto flotante daba Sharpe de 10¹⁶ (corregido con `metricas.EPS_VOL`).
- **Windows**: correr Python con `PYTHONUTF8=1`; no escribir scripts con heredocs de bash (rompen las barras).
- **El navegador integrado** del escritorio no abre `file://`: para mirar el reporte HTML se sirve con
  `python -m http.server` vía `preview_start` (configuración temporal fuera del repo).
