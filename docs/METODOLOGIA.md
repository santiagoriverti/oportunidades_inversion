# Metodología

Fórmulas y decisiones de cada paso, tal como están implementadas en `src/` (cada sección dice el módulo).
Notación: $P_t$ precio de cierre ajustado en USD; $r_t$ retorno simple; ventanas en días hábiles (21 = 1 mes,
63 = 3 meses, 252 = 1 año, 756 = 3 años).

## 1. Datos (`datos.py`, `universo.py`)

- **Fuente**: Yahoo Finance vía `yfinance`, cierres **ajustados** por dividendos y splits (`auto_adjust=True`):
  los retornos son totales. Se baja todo junto y se reintenta de a uno lo que falló.
- **Calendario**: días hábiles (lunes a viernes). Los feriados de cada bolsa se completan con el último precio
  hasta 5 días; BTC pierde sábado y domingo (su movimiento del fin de semana queda en el lunes). Un activo con más
  de 5 días hábiles sin cotizar queda en NaN y se informa.
- **Fecha de los datos**: el último cierre del benchmark (SPY). Si se corre con el mercado abierto, el último
  "cierre" es el precio del momento.
- **Moneda**: todo en USD. Los activos en otra moneda se multiplican por el tipo de cambio de Yahoo
  (`EURUSD=X`...); peniques (GBp) se dividen por 100. La moneda sale del universo, del sufijo del símbolo o de
  `fast_info` de Yahoo.
- **Inicio válido**: se descartan precios anteriores a la fecha de `inicio_valido` del universo (OKLO
  2024-05-10 y SMR 2022-05-03: antes Yahoo trae el SPAC, con precio plano de ~USD 10).
- **Tasa libre de riesgo**: T-bill de 13 semanas (`^IRX`, en %) — el último valor para optimizar y el promedio
  del período para los Sharpe históricos. Si falla, 4%.

## 2. Indicadores (`indicadores.py`)

Se calculan como **paneles** fecha × activo con ventanas que miran solo hacia atrás: el análisis toma la última
fila y el backtest la fila de cada rebalanceo (test `test_foto_sin_mirar_el_futuro`).

| Indicador | Fórmula |
|---|---|
| `ret_1m`, `ret_3m`, `ret_6m`, `ret_12m` | $P_t / P_{t-n} - 1$, $n$ = 21, 63, 126, 252 |
| `dist_sma50`, `dist_sma200` | $P_t / \text{SMA}_n(P)_t - 1$ |
| `zscore_1a` | $(\ln P_t - \overline{\ln P}_{252}) / s_{252}(\ln P)$ |
| `z_tendencia_3a` | residuo de la regresión $\ln P = a + b\,t$ en los últimos 756 días, dividido por el desvío de los residuos: $\hat e_t / \sqrt{\sum \hat e^2/(n-2)}$ (sumas móviles; igual a un `polyfit` por ventana) |
| `posicion_52s` | $(P_t - \min_{252}) / (\max_{252} - \min_{252})$ |
| `drawdown_52s` | $P_t / \max_{252}(P) - 1$; `drawdown_max`: contra el máximo de toda la historia bajada |
| `rsi_14` | RSI de Wilder: medias exponenciales ($\alpha = 1/14$) de subas $U$ y bajas $D$: $100\,U/(U+D)$ |
| `bollinger_pctb` | $(P_t - (m - 2s)) / (4s)$ con media $m$ y desvío $s$ de 20 días |
| `z_ret_3m` | $(r^{63}_t - \overline{r^{63}}) / s(r^{63})$ con la historia de retornos de 63 días de los últimos 756 días |
| `z_relativo_bench` | `zscore_1a` del precio relativo $P_t / P^{SPY}_t$ |
| `vol_1m`, `vol_1a`, `ratio_vol` | desvío de $\Delta \ln P$ en 21 / 252 días $\times \sqrt{252}$; cociente |
| `tendencia_alcista` | 1 si $\text{SMA}_{50} > \text{SMA}_{200}$ |
| `media_vida_dias` | sobre los residuos $e_t$ de la tendencia de 3 años: $\Delta e_t = \alpha + \beta e_{t-1}$, media vida $= -\ln 2 / \ln(1+\beta)$; NaN si $\beta \ge -0{,}0001$ (no revierte) |
| `hurst` | pendiente de $\log \sigma(x_{t+\tau} - x_t)$ contra $\log \tau$ con $x = \ln P$ (3 años, $\tau$ de 2 a 100): ≈0,5 paseo aleatorio, <0,5 revierte, >0,5 sigue la tendencia |

## 3. Score de oportunidad (`senales.py`)

1. Cada métrica $m$ con orientación $o_m$ ($-1$ si "más bajo = más barato") se pasa a percentil centrado dentro
   del universo: $p = (\text{rango}(o_m \cdot m) - 0{,}5)/n \in (0, 1)$.
2. Score de grupo = promedio de los percentiles disponibles × 100, si hay al menos 3 métricas técnicas, 2
   estadísticas o 2 fundamentales.

   | Grupo | Métricas (orientación) |
   |---|---|
   | técnico | `dist_sma50` (−), `dist_sma200` (−), `posicion_52s` (−), `rsi_14` (−), `bollinger_pctb` (−) |
   | estadístico | `zscore_1a` (−), `z_tendencia_3a` (−), `z_ret_3m` (−), `z_relativo_bench` (−) |
   | fundamental | `upside_analistas` (+), `pe_relativo_sector` (−), `peg` (−), `fcf_yield` (+) |

3. Score $= \sum_g w_g S_g / \sum_g w_g$ sobre los grupos disponibles (hace falta el técnico o el estadístico).
   Pesos por horizonte: corto 50/35/15, **mediano 40/30/30**, largo 25/25/50.
4. **Señales absolutas** (umbrales en `config.UMBRALES_SENALES`): `dist_sma200` < 0; `zscore_1a` ≤ −1,5;
   `z_tendencia_3a` ≤ −1,5; RSI ≤ 30; %B ≤ 0; `drawdown_52s` ≤ −25%; `z_ret_3m` ≤ −1,5; `z_relativo_bench` ≤ −1,5;
   upside ≥ 20%; P/E relativo ≤ 0,8; 0 < PEG < 1.
5. **Alertas**: *cuchillo que cae* (`ret_1m` ≤ −15%, debajo de la media de 50 días y SMA50 < SMA200); *posible
   trampa de valor* (P/E trailing / P/E forward − 1 ≤ −10%: el mercado espera menores ganancias); precio por
   encima del objetivo de los analistas; menos de 252 días de historia.
6. **Clasificación**: Oportunidad = score ≥ 70 y ≥ 2 señales (con alertas graves → *Oportunidad con alertas*);
   Vigilar = score ≥ 60 o ≥ 2 señales; Sobreextendida = score ≤ 30; si no, Neutral. Sin score: *Sin datos
   suficientes*.

**Fundamentales** (`fundamentales.py`, foto actual de `Ticker.info`, solo acciones): upside = objetivo promedio /
precio − 1 (si hay 3+ analistas); P/E relativo = P/E trailing / P/E trailing del ETF SPDR del sector (XLK, XLV,
XLF, XLE, XLP, XLY, XLI, XLC, XLB, XLU, XLRE); PEG (`trailingPegRatio`, solo positivo); FCF yield = flujo de caja
libre / capitalización; dividendo = `dividendRate` / precio. ADRs que reportan en otra moneda (VALE: BRL) mezclan
monedas en el EPS y el flujo de caja: para ellos se descartan P/E trailing, PEG, P/E relativo y FCF yield.

## 4. Métricas de riesgo y performance (`metricas.py`)

Con retornos simples de $N$ períodos y $k$ períodos por año (252 diarios, 52 semanales); $r_f^{(k)} = (1+r_f)^{1/k} - 1$:

- Retorno anual (CAGR) $= \left(\prod (1 + r_t)\right)^{k/N} - 1$; volatilidad $= s(r)\sqrt{k}$.
- **Sharpe** $= \overline{(r - r_f^{(k)})}\,k / (s(r)\sqrt{k})$ (media aritmética del exceso; NaN si $s \approx 0$).
- **Sortino** igual, con la desviación a la baja $\sqrt{\overline{\min(r - r_f^{(k)}, 0)^2}}\sqrt{k}$.
- Máxima caída $= \min_t (V_t / \max_{s \le t} V_s - 1)$, $V$ = valor acumulado; **Calmar** = CAGR / |máx. caída|.
- **VaR 95%** $= -q_{0,05}(r)$; **CVaR 95%** $= -\mathbb{E}[r \mid r \le q_{0,05}]$ (históricos, de un período).
- **Beta** $= \text{cov}(r - r_f, r_m - r_f)/\text{var}(r_m - r_f)$; **alfa de Jensen** anual
  $= (\overline{r - r_f} - \beta\,\overline{r_m - r_f})\,k$; con retornos **semanales** (asincronía horaria).

Las métricas por activo usan la ventana del horizonte (3 años en "mediano"): diarias para riesgo/retorno,
semanales para beta, alfa y correlación.

## 5. Modelo de riesgo (`riesgo.py`)

- **Ventana**: últimos `ventana_anios`; entran los activos con precio en al menos 90% de los días y precio
  reciente. Se sacan los gemelos y recién después se recorta la ventana a desde que todos tienen datos (si no,
  un gemelo joven como IBIT acortaría la ventana de todos).
- **Retornos semanales** (viernes). Con diarios, la correlación de BTC y de los ETFs de Xetra con EE.UU. sale
  artificialmente baja (medido el 2026-11-06: XLK/QDVE 0,56 diaria vs 0,92 semanal; SMH/VVSM 0,68 vs 0,94).
- **Gemelos**: correlación semanal ≥ 0,99 **y** volatilidades a menos de 1,25 veces (SSO, 2x, no es gemelo de
  SPY). Representante: más historia; desempata benchmark, mayor patrimonio/capitalización, orden de la lista.
- **Covarianza**: Ledoit-Wolf (scikit-learn, objetivo identidad escalada) × 52.
- **Retornos esperados**: `historico` = CAGR de la ventana (por defecto) o `capm` = $r_f + \beta(\mu_m - r_f)$.
- **Black-Litterman**: equilibrio $\Pi = \delta \Sigma w$ con $w$ = pesos iguales (no hay capitalizaciones
  comparables entre acciones, ETFs y cripto) y $\delta = (\mu_m - r_f)/\sigma_m^2$ acotado a [1, 6] (2,5 si el
  mercado rindió menos que $r_f$). Vista absoluta por activo: $q_i = \Pi_i + 0{,}25\, z_i\, \sigma_i$ con
  $z_i = (\text{score}_i - 50)/50$ (un score de 100 suma 0,25 de Sharpe). $\Omega = \text{diag}(\tau P\Sigma P')$,
  $\tau = 0{,}05$. Posterior: $\mu_{BL} = \Pi + \tau\Sigma P'(P\tau\Sigma P' + \Omega)^{-1}(q - P\Pi)$.

## 6. Portafolios (`portafolios.py`, `estrategias.py`)

Restricciones comunes: $w_i \ge 0$, $\sum w_i = 1$, $w_i \le$ `peso_maximo` (20%; si $n \cdot$ tope $< 1$ se usa
$1/n$). Los optimizados (mínima varianza, máximo Sharpe, volatilidad objetivo, Black-Litterman) eliminan
posiciones menores a `peso_minimo` (2%) de a una y renormalizan; a todos se les reaplica el tope repartiendo el
excedente en proporción.

| Portafolio | Problema |
|---|---|
| Pesos iguales | $w_i = 1/n$ |
| Mínima varianza | $\min w'\Sigma w$ (SLSQP) |
| Máximo Sharpe | formulación convexa con $y = w/\kappa$: $\min y'\Sigma y$ s.a. $(\mu - r_f)'y = 1$, $\sum y = \kappa$, $0 \le y_i \le \text{tope}\cdot\kappa$; si ningún portafolio factible supera $r_f$ → mínima varianza |
| Volatilidad objetivo | $\max \mu'w$ s.a. $w'\Sigma w \le \sigma^{*2}$ ($\sigma^*$ = 10%) |
| Paridad de riesgo | $\min \tfrac12 y'\Sigma y - \sum \tfrac1n \ln y_i$ y $w = y/\sum y$ (Spinu 2013): contribuciones $w_i(\Sigma w)_i/w'\Sigma w$ iguales |
| HRP | distancia $d_{ij} = \sqrt{(1-\rho_{ij})/2}$, enlace simple, orden de las hojas y bisección recursiva con peso $\alpha = 1 - V_1/(V_1+V_2)$ ($V$ = varianza de cada mitad con pesos de varianza inversa) |
| Black-Litterman | máximo Sharpe con $\mu_{BL}$ |
| Oportunidades | paridad de riesgo entre las `top_n_oportunidades` (10) con mejor score clasificadas como oportunidad (si un gemelo excluido está en el top, entra su representante) |

**Frontera eficiente**: mínima varianza para 30 retornos objetivo entre el de mínima varianza y el máximo
factible. El resumen muestra retorno, volatilidad y Sharpe **ex-ante** (todos con el mismo $\mu$ histórico, para
compararlos) y la versión histórica en la ventana con esos pesos (`_hist`).

## 7. Qué comprar (`asignacion.py`)

Cantidad entera $\lfloor w_i C / p_i \rfloor$ y después, con lo que sobra, de a una unidad la posición con mayor
déficit $w_i C - q_i p_i$ si el déficit supera media unidad y alcanza la plata (nunca se gasta más que $C$).
Cripto: fracciones de 4 decimales. **CEDEARs**: precio de la especie D (dólar MEP) de data912; si solo cotiza en
pesos, precio / MEP implícito (mediana de pesos/D entre los CEDEARs con ambas especies). Si el representante de
gemelos no tiene CEDEAR pero un equivalente sí (BTC-USD → IBIT), se usa ese.

## 8. Backtest (`backtest.py`)

En el último día hábil de cada trimestre (mes en "corto", semestre en "largo"), desde que hay una ventana
completa: indicadores y score a esa fecha (**sin fundamentales**), portafolios con `armar_portafolios` (la misma
función que hoy, con datos hasta esa fecha), tenencia comprar-y-mantener hasta el próximo rebalanceo, costo
`costo_bps` × rotación $\sum|w^{nuevo} - w^{derivado}|$ el primer día. Un período sin portafolio queda en
efectivo. **IC** = correlación de Spearman entre el score y el retorno hasta el próximo rebalanceo; se informa la
media, su estadístico t ($\bar{IC}/(s/\sqrt{n})$) y el exceso de las oportunidades contra el promedio.

Sesgos: universo elegido hoy (supervivencia), sin fundamentales históricos, sin impuestos.

## 9. Seguimiento ex-post (`expost.py`)

Para cada corrida guardada se vuelve a bajar todo (Yahoo reajusta hacia atrás los precios con cada dividendo:
nunca se mezclan precios bajados en días distintos). Base = cierre de `fecha_datos`; cada portafolio se compra en
la base y se mantiene; se compara con el benchmark en el mismo período y a 21/63/126/252 días. Anualizados,
volatilidad y Sharpe solo con 63 días o más. Señales: retorno de cada activo, promedio por clasificación, IC
score-retorno y % de oportunidades que le ganaron al benchmark. Ranking: exceso medio y % de corridas en que cada
estrategia le ganó al benchmark.

## Referencias

Markowitz (1952) *Portfolio Selection*; Sharpe (1966, 1994); Sortino y Price (1994); Jensen (1968); Wilder (1978)
*New Concepts in Technical Trading Systems*; Bollinger (2001); Black y Litterman (1992); He y Litterman (1999);
Ledoit y Wolf (2004) *Honey, I Shrunk the Sample Covariance Matrix*; Cornuejols y Tütüncü (2007) *Optimization
Methods in Finance*; Maillard, Roncalli y Teïletche (2010); Spinu (2013) *An Algorithm for Computing Risk Parity
Weights*; López de Prado (2016) *Building Diversified Portfolios that Outperform Out of Sample*; Hurst (1951).
