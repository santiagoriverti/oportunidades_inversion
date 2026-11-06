# CLAUDE.md — instrucciones para sesiones de Claude en este repo

## Al empezar
1. `git pull` antes de cualquier cambio (el usuario trabaja desde más de una PC).
2. Leer **`ESTADO.md`**: decisiones tomadas, qué está hecho y la lista ordenada de lo que falta.
3. El método de cada parte está en el docstring de su módulo de `src/` (y, cuando exista, `docs/METODOLOGIA.md`).

## Reglas del usuario
- **Commits solo con el usuario (Santiago Riverti). NUNCA agregar `Co-Authored-By: Claude`** ni ninguna
  atribución a Claude en commits o PRs.
- Idioma: español rioplatense en respuestas, commits, documentación y textos de los notebooks.
- El usuario corre los notebooks en **Google Colab** desde los badges del README; cada notebook clona el
  repo, así que un cambio no llega a Colab hasta que se pushea. El repo es **público**.
- Cada notebook termina descargando un ZIP con todo (Excel + reporte HTML + corrida).
- Registro de corridas en Google Drive (`Mi unidad/oportunidades_inversion/registros`).

## Reglas técnicas que muerden
- Windows: correr Python con `PYTHONUTF8=1`. No escribir scripts con heredocs de bash (rompen `\`).
- Los `.ipynb` se generarán con `scripts/gen_notebooks.py`: no editarlos a mano.
- Colab reutiliza sesiones: la celda SETUP debe hacer `git fetch` + `reset --hard` y purgar `src.*` de
  `sys.modules` (lección de los otros repos del usuario).
- Yahoo: precios ajustados cambian hacia atrás con cada dividendo (el ex-post vuelve a bajar todo);
  `dividendYield` viene en %; ADRs con `financialCurrency` ≠ `currency` mezclan monedas; yfinance 1.x
  devuelve columnas MultiIndex (Price, Ticker).
- Retornos semanales para covarianza/correlación (BTC y ETFs europeos no cotizan sincronizados con EE.UU.).
- Antes de commitear: `python -m pytest` (cuando existan los tests) y `python scripts/probar_local.py --rapido`.

## Cierre de sesión
Actualizar `ESTADO.md` (fecha, hecho, falta) y, cuando exista, `.claude/memory/project.md`. Commit + push
si el usuario lo pidió (si el push pide credenciales, lo hace el usuario).
