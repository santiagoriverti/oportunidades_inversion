# ESTADO — oportunidades_inversion

**Última actualización:** 2026-11-06 (sesión 1, cortada por límite de uso). Punto de entrada para retomar:
este archivo → `CLAUDE.md` (reglas) → código en `src/` (cada módulo tiene un docstring con su método).

## 0. Estado en una línea

**Motor de análisis en Python TERMINADO y probado con datos reales** (`python scripts/probar_local.py --rapido`
corre de punta a punta en ~25 s). **FALTAN**: notebooks de Colab, README con badges, docs y tests (§3).

## 1. Objetivo (pedido del usuario, 2026-11-06)

Notebook de Colab, abrible desde el README, donde el usuario edita una lista de tickers y obtiene:
1. qué activos están **artificialmente bajos** (métricas técnicas, estadísticas y fundamentales avanzadas);
2. **portafolios** que maximizan retorno minimizando varianza (Markowitz, Sharpe, etc.) y **qué comprar**;
3. **registro** de cada corrida para medir después (ex-post) cómo le fue a cada alternativa.

## 2. Decisiones tomadas (preguntas respondidas por el usuario el 2026-11-06)

| Tema | Decisión |
|---|---|
| Registro de corridas | **Google Drive** (`Mi unidad/oportunidades_inversion/registros/AAAAMMDD_HHMMSS/`); en la PC `registros_local/` |
| AO28, HJCLO, NPCDO, YMCXO (bono/ONs de BYMA) | **Excluidos** (sin historia gratis en Yahoo ni data912). Módulo de renta fija (TIR/duration) → roadmap |
| Qué comprar | **Ambos**: acciones/ETFs de EE.UU. y **CEDEARs** (data912, especie D en USD MEP; si solo hay pesos, MEP implícito) |
| Horizonte | **Mediano (6-12 meses)**: ventana 3 años, rebalanceo trimestral, seguimiento a 1/3/6/12 meses |
| Correcciones de tickers (decididas por Claude, en `data/universo.csv` columna `nota`) | `UN` excluido (es otro ETF; NU ya está) · `VGII`→`VGIT` · `^IXIC` solo referencia · `BRKB`→`BRK-B` · `BTC`→`BTC-USD` · EXX1/QDVE/VVSM en `.DE` (EUR→USD) · OKLO desde 2024-05-10 y SMR desde 2022-05-03 (antes = precios de SPAC) |

Decisiones metodológicas clave (detalle en los docstrings de `src/`):
- Covarianza con **retornos semanales** + Ledoit-Wolf (con diarios, BTC y ETFs de Xetra muestran correlación
  falsa baja con EE.UU.: XLK/QDVE 0,56 diaria vs 0,92 semanal).
- **Gemelos** (corr. semanal ≥ 0,99 y vol. parecida): se optimiza con uno (SPY≈VOO≈VTI, GLD≈IAU, QQQ≈QQQM,
  BTC≈IBIT, XLK≈VGT≈IYW, VNQ≈SCHH). SSO (2x) NO es gemelo de SPY. Se sacan antes de recortar la ventana.
- Score de oportunidad = percentiles (técnico 40%, estadístico 30%, fundamental 30%) + señales absolutas;
  "Oportunidad" = score ≥ 70 y ≥ 2 señales; alertas (cuchillo que cae, trampa de valor...).
- 8 portafolios: 1/N, mínima varianza, máximo Sharpe, volatilidad objetivo (10%), paridad de riesgo, HRP,
  Black-Litterman con vistas = score, oportunidades (paridad de riesgo del top 10). Peso máx. 20%.
- Fundamentales de Yahoo: `dividendYield` viene en %, ADRs con `financialCurrency` distinta (VALE) mezclan
  monedas → se descartan esas métricas.

## 3. Qué está hecho y qué falta

**Hecho (sin commitear antes de esta sesión; ver git log):**
- `data/universo.csv` (87 tickers: 81 activos, 1 referencia, 5 excluidos).
- `src/`: config, universo, datos, fundamentales, indicadores, senales, metricas, riesgo, portafolios,
  estrategias, asignacion, backtest, registro, expost, graficos (paleta validada con el skill dataviz),
  tablas, exportar, pipeline (clase `Analisis`).
- `scripts/probar_local.py` (corrida completa local). Probado solo en modo `--rapido` (sin fundamentales ni
  backtest); `fundamentales.py` se probó aparte con 7 tickers.

**Falta (en este orden):**
1. Correr `python scripts/probar_local.py` COMPLETO (con fundamentales y backtest) y corregir errores.
2. `tests/` con datos sintéticos (indicadores, métricas, portafolios, asignación, registro/ex-post, backtest
   sin look-ahead, universo, notebooks) + `.github/workflows/tests.yml` (Python 3.12).
3. `scripts/gen_notebooks.py` → `notebooks/01_oportunidades_y_portafolios.ipynb` y
   `notebooks/02_seguimiento_expost.ipynb` (patrón SETUP de los otros repos: clonar/actualizar con
   `git fetch --depth 1` + `reset --hard`, purgar `src.*`, `pip install -U yfinance`, montar Drive, terminar
   con ZIP). Probar con nbconvert en `_local_run/`.
4. Corrida de ejemplo en `data/ejemplo_registro/` (`probar_local.py --guardar-en data/ejemplo_registro`) para
   que el notebook 02 muestre algo sin corridas propias.
5. Docs: `README.md` (badges de Colab, uso, métricas, portafolios, aviso legal), `CONTEXTO.md`,
   `docs/METODOLOGIA.md`, `docs/ARQUITECTURA.md`, `docs/ROADMAP.md`, `CHANGELOG.md`,
   `.claude/memory/project.md`; memoria global `~/.claude/memory/projects/oportunidades_inversion.md` + core.md.
6. Revisar los gráficos renderizados (abrir el HTML del ZIP) y verificar el link de Colab.

## 4. Cómo correr en una PC nueva

```bash
git clone https://github.com/santiagoriverti/oportunidades_inversion.git
cd oportunidades_inversion
pip install -r requirements.txt
PYTHONUTF8=1 python scripts/probar_local.py --rapido
```
