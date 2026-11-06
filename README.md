# Oportunidades de inversión

[![tests](https://github.com/santiagoriverti/oportunidades_inversion/actions/workflows/tests.yml/badge.svg)](https://github.com/santiagoriverti/oportunidades_inversion/actions/workflows/tests.yml)

Detecta qué activos de una lista están **artificialmente bajos**, arma **portafolios óptimos** (Markowitz, máximo
Sharpe, paridad de riesgo, HRP, Black-Litterman...), dice **qué comprar** (acciones/ETFs de EE.UU. o CEDEARs) y
**registra cada corrida** para medir después, con precios reales, cómo le fue a cada alternativa.

Todo corre en **Google Colab** desde el navegador: no hace falta instalar nada.

> ⚠️ **Herramienta educativa y de análisis cuantitativo. No es asesoramiento financiero ni una recomendación de
> compra o venta.** Que un activo esté "barato" contra su historia no garantiza que vaya a subir; los rendimientos
> pasados no garantizan rendimientos futuros.

---

## Notebooks

| Notebook | Qué hace | Abrir |
|---|---|---|
| `01_oportunidades_y_portafolios` | Elegís los tickers → score de oportunidad, métricas de riesgo, 8 portafolios con frontera eficiente, qué comprar (EE.UU. y CEDEARs), backtest walk-forward, registro en Google Drive y ZIP con Excel + reporte HTML. | [![Abrir en Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/santiagoriverti/oportunidades_inversion/blob/main/notebooks/01_oportunidades_y_portafolios.ipynb) |
| `02_seguimiento_expost` | Lee las corridas guardadas en tu Drive y mide cuánto rindió cada portafolio desde su fecha (contra SPY, a 1/3/6/12 meses), si las "Oportunidades" le ganaron al resto, y arma un ranking de estrategias. | [![Abrir en Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/santiagoriverti/oportunidades_inversion/blob/main/notebooks/02_seguimiento_expost.ipynb) |

> **¿Ves una versión vieja en Colab?** El badge siempre abre la última versión de GitHub, pero si guardaste una
> copia en tu Drive, Colab puede abrir esa. Para actualizar: borrá la copia de `Mi unidad/Colab Notebooks/` y
> volvé a hacer clic en el badge. El código (`src/`) siempre se baja actualizado al correr la primera celda.

## Cómo usarlo

1. Clic en **Abrir en Colab** del notebook 01.
2. En la celda **1. Configuración** escribí tus tickers (o dejá `TICKERS = None` para la lista por defecto de 81
   activos), el horizonte (`corto`, `mediano`, `largo`) y el capital.
3. *Entorno de ejecución → Ejecutar todas*. Tarda 2-3 minutos. La primera vez Colab pide permiso para usar tu
   Google Drive (ahí se guarda el registro). Al final se descarga un ZIP con el Excel y el reporte.
4. Cada tanto (semanas o meses después) abrí el **notebook 02** para ver cómo les fue a las corridas guardadas.

Los tickers son los de [Yahoo Finance](https://finance.yahoo.com): acciones y ETFs de EE.UU. tal cual (`AAPL`,
`SPY`), cripto con `-USD` (`BTC-USD`), otras bolsas con sufijo (`SAP.DE`, `IUIT.L`). Todo se convierte a dólares.

---

## Qué calcula

### 1. ¿Qué está artificialmente bajo? — score de oportunidad (0-100)

Cada métrica se pasa a **percentil dentro de la lista** (100 = el más barato) y se promedia por grupo; el score
pondera los grupos según el horizonte (mediano: 40% técnico, 30% estadístico, 30% fundamental).

| Grupo | Métricas |
|---|---|
| Técnico | precio vs media de 50 y 200 días · posición en el rango de 52 semanas · RSI 14 · %B de Bollinger |
| Estadístico | z-score del log-precio en 1 año · desvío contra su tendencia de 3 años · z-score de la caída de 3 meses · z-score contra el benchmark |
| Fundamental (acciones) | upside del precio objetivo de los analistas · P/E contra el ETF SPDR de su sector · PEG · rendimiento del flujo de caja libre |

Como el score es relativo, también se cuentan **señales absolutas** (debajo de la media de 200 días, RSI ≤ 30,
−25% desde el máximo de 52 semanas, upside ≥ 20%, P/E 20% debajo de su sector...).

- **Oportunidad**: score ≥ 70 y al menos 2 señales. **Oportunidad con alertas**: además tiene una alerta —
  *cuchillo que cae* (−15% en un mes en tendencia bajista), *posible trampa de valor* (ganancias esperadas en
  baja) o precio por encima del objetivo de los analistas.
- **Vigilar**, **Neutral** y **Sobreextendida** (score ≤ 30).
- Información extra: media vida de reversión a la tendencia y exponente de Hurst.

### 2. Riesgo y retorno

Retorno anual compuesto, volatilidad, **Sharpe**, **Sortino**, máxima caída, **Calmar**, **VaR y CVaR** al 95%,
asimetría, curtosis, **beta, alfa y correlación** contra el benchmark (SPY).

### 3. Portafolios (sin ventas en corto, tope de 20% por activo)

| Portafolio | Idea |
|---|---|
| Pesos iguales (1/N) | referencia ingenua y difícil de vencer |
| Mínima varianza | el menor riesgo posible |
| Máximo Sharpe (Markowitz) | portafolio tangente: máximo retorno por unidad de riesgo |
| Volatilidad objetivo | máximo retorno con volatilidad ≤ 10% (configurable) |
| Paridad de riesgo | cada activo aporta el mismo riesgo |
| HRP (López de Prado) | asignación jerárquica por grupos de activos parecidos |
| Black-Litterman con señales | equilibrio inclinado hacia los activos con mejor score de oportunidad |
| Oportunidades | las 10 mejores oportunidades, con paridad de riesgo |

La covarianza se estima con **retornos semanales** (BTC y los ETFs europeos no cotizan en el mismo horario que
EE.UU.: con retornos diarios su correlación sale artificialmente baja) y contracción de **Ledoit-Wolf**. Los
activos casi idénticos (*gemelos*: SPY/VOO/VTI, GLD/IAU, QQQ/QQQM, BTC/IBIT, VGT/XLK/IYW, VNQ/SCHH) se optimizan
como uno solo y se sugiere el equivalente de menor costo.

### 4. Qué comprar

Cantidades enteras para tu capital en dos versiones: **EE.UU.** (acciones/ETFs originales; cripto fraccionada) y
**CEDEARs** (especie D en dólar MEP con precios en vivo de [data912](https://data912.com); si solo cotiza en pesos
se usa el MEP implícito; lo que no tiene CEDEAR se marca para comprar afuera).

### 5. Backtest walk-forward y registro

En cada trimestre se recalcula todo **solo con los datos de ese momento**, se mantiene hasta el próximo
rebalanceo y se descuentan costos. También se mide si el score **anticipó** los retornos (IC de Spearman). Cada
corrida se guarda en `Mi unidad/oportunidades_inversion/registros/AAAAMMDD_HHMMSS/` (señales, pesos, cantidades
y precios) para el seguimiento ex-post del notebook 02.

Fórmulas y decisiones: [docs/METODOLOGIA.md](docs/METODOLOGIA.md).

---

## Corrida de ejemplo (lista por defecto, datos al 06/11/2026)

Guardada en [`data/ejemplo_registro/`](data/ejemplo_registro/) (el notebook 02 la usa si no tenés corridas propias).

- **Clasificación de los 81 activos**: 13 Oportunidad, 5 Oportunidad con alertas, 38 Vigilar, 7 Neutral,
  18 Sobreextendida. Top 10: GRID, AIRR, SPMO, AVGO, IEMG, EWZ, VALE, FICO, VVSM.DE, COPX.
- **Portafolios** (ventana 07/11/2023 → 06/11/2026; retorno esperado = histórico de la ventana):

  | Portafolio | Retorno esp. | Volatilidad | Sharpe | Activos |
  |---|---|---|---|---|
  | Mínima varianza | 13,1% | 6,5% | 1,40 | 12 |
  | Máximo Sharpe (Markowitz) | 37,4% | 13,7% | 2,44 | 12 |
  | Volatilidad objetivo (10%) | 28,2% | 10,1% | 2,39 | 13 |
  | Paridad de riesgo | 11,9% | 10,0% | 0,79 | 71 |
  | Black-Litterman con señales | 17,0% | 18,3% | 0,71 | 22 |

  Los Sharpe ex-ante de Markowitz son altos porque usan el retorno pasado (oro, bancos europeos y Berkshire
  subieron mucho en la ventana): **no son una predicción**.
- **Backtest** (rebalanceo trimestral, dic-2021 → nov-2026, costos de 10 pb): Máximo Sharpe 16,2% anual (máx.
  caída −28,6%), Oportunidades 15,5%, 1/N 12,5%, SPY 10,5%, Mínima varianza 5,1%. Tiene **sesgo de
  supervivencia** (la lista se armó hoy, con ganadores conocidos).
- **¿El score anticipó los retornos?** En el backtest, **no**: IC medio +0,003 (t = 0,05) en 20 trimestres; las
  oportunidades le ganaron al promedio de la lista en el 50% de los trimestres (+0,7% en promedio). Detectar
  activos baratos no alcanza para predecir el trimestre siguiente: por eso el seguimiento ex-post es parte del
  proyecto.

## Lista por defecto

[`data/universo.csv`](data/universo.csv): los 87 tickers de la lista original con su rubro, nombre, moneda y
correcciones (columna `nota`). 81 se analizan; `^IXIC` (índice Nasdaq Composite) queda como referencia;
quedan **excluidos** AO28, HJCLO, NPCDO e YMCXO (bono y obligaciones negociables de BYMA: no hay historia de
precios gratuita y se evalúan por TIR, no por precio) y `UN` (en Yahoo es otro ETF; Nu Bank ya está como `NU`).
Otras correcciones: `VGII` → `VGIT`, `BRKB` → `BRK-B`, `BTC` → `BTC-USD`, EXX1/QDVE/VVSM en Xetra (EUR → USD),
OKLO y SMR sin los precios de su SPAC previo.

## Limitaciones

- Los datos son de Yahoo Finance vía `yfinance` (gratis, sin garantías: a veces cambia o corta pedidos).
- Los fundamentales son una **foto actual** (Yahoo no da su historia gratis): no entran en el backtest.
- El retorno esperado histórico de Markowitz premia lo que ya subió; mirá también los portafolios robustos.
- Backtest con sesgo de supervivencia y sin impuestos; costos simplificados.
- Bonos y ONs argentinas: fuera de esta versión (ver [docs/ROADMAP.md](docs/ROADMAP.md)).

## Estructura

```
notebooks/   01_oportunidades_y_portafolios.ipynb, 02_seguimiento_expost.ipynb (generados por scripts/gen_notebooks.py)
src/         el motor (un módulo por tema; clase Analisis en pipeline.py) — ver docs/ARQUITECTURA.md
data/        universo.csv (lista por defecto) y ejemplo_registro/ (corrida de ejemplo)
scripts/     gen_notebooks.py, probar_local.py (corrida completa en la PC)
tests/       tests con datos sintéticos (corren en GitHub Actions con Python 3.12, como Colab)
docs/        METODOLOGIA.md, ARQUITECTURA.md, ROADMAP.md
```

## Correr en la PC

```bash
git clone https://github.com/santiagoriverti/oportunidades_inversion.git
cd oportunidades_inversion
pip install -r requirements.txt
python -m pytest
python scripts/probar_local.py --rapido     # sin fundamentales ni backtest (~25 s)
python scripts/probar_local.py              # todo (~1 minuto); ZIP en _descargas/, corrida en registros_local/
```

En Windows conviene `set PYTHONUTF8=1` (o `PYTHONUTF8=1 python ...` en Git Bash).

## Documentación

| Archivo | Para qué |
|---|---|
| [docs/METODOLOGIA.md](docs/METODOLOGIA.md) | fórmulas de cada métrica, score, optimizadores, backtest y seguimiento |
| [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) | módulos, flujo de datos, formato del registro, cómo extenderlo |
| [docs/ROADMAP.md](docs/ROADMAP.md) | ideas y pendientes |
| [CONTEXTO.md](CONTEXTO.md) | decisiones, fuentes y trampas conocidas |
| [ESTADO.md](ESTADO.md) | estado actual y cómo retomar (punto de entrada para desarrollar) |
| [CHANGELOG.md](CHANGELOG.md) | versiones |
