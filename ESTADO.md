# ESTADO — oportunidades_inversion

**Última actualización:** 2026-11-06 (sesión 1, cierre). Punto de entrada para retomar:
este archivo → `CLAUDE.md` (reglas) → `CONTEXTO.md` (decisiones y trampas) → `docs/METODOLOGIA.md` y
`docs/ARQUITECTURA.md` → `.claude/memory/project.md` (historial).

## 0. Estado en una línea

**Versión 0.1.0 completa y pusheada**: motor en `src/`, notebooks 01 (análisis) y 02 (seguimiento) con badges de
Colab en el README, corrida de ejemplo, 57 tests con CI y documentación. Verificado en la PC (análisis completo,
notebooks ejecutados con nbconvert, reporte revisado). **Pendiente: que el usuario corra los notebooks en Colab.**

## 1. Qué hay

| Pieza | Dónde | Estado |
|---|---|---|
| Lista por defecto (87 tickers, 81 analizados) | `data/universo.csv` | al día (2026-11-06) |
| Motor de análisis (clase `Analisis`) | `src/` (18 módulos) | probado con datos reales |
| Notebook 01: oportunidades, portafolios, qué comprar, backtest, registro, ZIP | `notebooks/01_oportunidades_y_portafolios.ipynb` | ejecutado local sin errores |
| Notebook 02: seguimiento ex-post | `notebooks/02_seguimiento_expost.ipynb` | ejecutado local sin errores |
| Corrida de ejemplo (usada por el 02 si no hay corridas propias) | `data/ejemplo_registro/20261106_204148/` | datos al 2026-11-06 |
| Generador de notebooks | `scripts/gen_notebooks.py` | — |
| Corrida completa en la PC | `scripts/probar_local.py` | ~60 s completa, ~25 s `--rapido` |
| Tests (sintéticos, sin red) | `tests/` (57) + `.github/workflows/tests.yml` (Python 3.12) | 57 OK en la PC |

## 2. Verificación hecha (2026-11-06)

- `python scripts/probar_local.py` (lista por defecto, fundamentales y backtest): sin errores, 59 s.
- Notebooks 01 y 02 ejecutados con `jupyter nbconvert --execute` en `_local_run/`: todas las celdas OK.
- Reporte HTML del ZIP revisado en el navegador integrado (ranking, mapa de señales, precios, frontera, pesos,
  aporte al riesgo, correlaciones, backtest, IC); corregidos: título pisado por la leyenda, etiquetas encimadas
  en la frontera, escala de pesos aplastada por la fila "otros", tablas sin formato.
- `python -m pytest`: 57 OK.
- **Colab: no verificado** (necesita la cuenta de Google del usuario). Qué mirar en la primera corrida: que la
  celda SETUP imprima `Versión del repo:` con el último commit, que monte el Drive y que se descargue el ZIP.

## 3. Cifras vigentes (corrida de ejemplo, datos al 2026-11-06)

- 81 activos: 13 Oportunidad, 5 Oportunidad con alertas, 38 Vigilar, 7 Neutral, 18 Sobreextendida.
  Top 10: GRID, AIRR, SPMO, AVGO, IEMG, EWZ, VALE, FICO, VVSM.DE, COPX.
- Ventana de optimización 2023-11-07 → 2026-11-06 (784 días); 71 activos optimizables (OKLO y XE fuera por
  historia; 8 gemelos). Tasa libre de riesgo 4,00% (^IRX). MEP implícito ~1.560.
- Máximo Sharpe ex-ante 37,4% / vol 13,7% / Sharpe 2,44 (GLD 20%, EXX1.DE 20%, BRK-B 10%...); mínima varianza
  13,1% / 6,5%; volatilidad objetivo 28,2% / 10,1%.
- Backtest dic-2021 → nov-2026 (20 rebalanceos trimestrales, 10 pb): Máximo Sharpe 16,2% anual (Sharpe 0,69,
  caída máx. −28,6%), Oportunidades 15,5%, Volatilidad objetivo 9,6%, 1/N 12,5%, Black-Litterman 12,0%, Paridad
  8,5%, SPY 10,5%, HRP 6,6%, Mínima varianza 5,1%.
- IC del score: +0,003 (t = 0,05), positivo en 40% de los trimestres; oportunidades +0,7% por trimestre contra el
  promedio, ganan en 50% → el score **no** predijo retornos trimestrales.

Estas cifras se citan en `README.md` (sección "Corrida de ejemplo"), `CONTEXTO.md` §4 y aquí: si se regenera la
corrida de ejemplo, actualizar los tres.

## 4. Próximos pasos

1. El usuario corre el notebook 01 y el 02 en Colab (desde los badges del README). Si algo falla, pegar el error
   en una sesión nueva: casi seguro es de versiones de Colab (pandas/plotly/yfinance).
2. Ideas en `docs/ROADMAP.md` (renta fija argentina por TIR, valuación contra la propia historia, robot semanal,
   mínimo CVaR, restricciones por sector...).

## 5. Rutina

- **Usar**: badge del notebook 01 → configurar → *Ejecutar todas*; semanas después, badge del notebook 02.
- **Cambiar código**: editar `src/` (o `scripts/gen_notebooks.py` y regenerar) → `python -m pytest` →
  `python scripts/probar_local.py --rapido` → commit + push (Colab toma el cambio al correr la celda SETUP).
- **Probar un notebook en la PC**: `cp notebooks/*.ipynb _local_run/` y
  `python -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=900 _local_run/<nb>`.
- **Regenerar la corrida de ejemplo** (si cambia el formato del registro): borrar la carpeta de
  `data/ejemplo_registro/` y correr `python scripts/probar_local.py --guardar-en data/ejemplo_registro --sin-zip`;
  actualizar las cifras de §3, README y CONTEXTO.

## 6. PC nueva

```bash
git clone https://github.com/santiagoriverti/oportunidades_inversion.git
cd oportunidades_inversion
pip install -r requirements.txt
PYTHONUTF8=1 python -m pytest
PYTHONUTF8=1 python scripts/probar_local.py --rapido
```
