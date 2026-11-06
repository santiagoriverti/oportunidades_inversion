# CLAUDE.md — instrucciones para sesiones de Claude en este repo

## Al empezar
1. `git pull` antes de cualquier cambio (el usuario trabaja desde más de una PC).
2. Leer **`ESTADO.md`** (estado, verificación, cifras vigentes, próximos pasos, rutina, PC nueva).
3. Si hay que tocar cálculos: **`CONTEXTO.md`** (decisiones y trampas) y **`docs/METODOLOGIA.md`** (fórmulas);
   para la estructura del código, **`docs/ARQUITECTURA.md`**. Historial: `.claude/memory/project.md`.

## Reglas del usuario
- **Commits solo con el usuario (Santiago Riverti). NUNCA agregar `Co-Authored-By: Claude`** ni ninguna
  atribución a Claude en commits o PRs. Commit/push cuando el usuario lo pide.
- Idioma: español rioplatense en respuestas, commits, documentación y textos de los notebooks.
- El usuario corre los notebooks en **Google Colab** desde los badges del README; cada notebook clona el repo, así
  que un cambio no llega a Colab hasta que se pushea. El repo es **público**: nada de datos personales ni rutas
  de la PC en lo que se versiona (el registro guarda `ruta_universo` relativa).
- Cada notebook termina descargando un ZIP con todo (Excel + reporte HTML + carpeta de la corrida).
- Registro de corridas en Google Drive (`Mi unidad/oportunidades_inversion/registros`), decisión del usuario.
- No es asesoramiento financiero: mantener el aviso en README, notebooks, Excel y reporte.

## Reglas técnicas que muerden
- Windows: correr Python con `PYTHONUTF8=1`. **No escribir scripts ni ediciones con heredocs de bash** (rompen
  `\`): usar las herramientas de archivos o un `.py` aparte.
- **Los `.ipynb` se generan con `python scripts/gen_notebooks.py`**: no editarlos a mano ni con NotebookEdit; se
  versionan sin salidas (`tests/test_notebooks.py` lo controla).
- **Colab reutiliza sesiones**: la celda SETUP hace `git fetch --depth 1` + `git reset --hard FETCH_HEAD`, purga
  `src.*` de `sys.modules` y actualiza yfinance. No sacar nada de eso.
- Compatibilidad con Colab (Python 3.12, pandas 2.2, plotly 5.x): no usar alias `"ME"`/`"QE"`, ni APIs de plotly
  nuevas sin `try` (ver `graficos._estilo`), ni sintaxis de Python > 3.10.
- Yahoo: precios ajustados cambian hacia atrás con cada dividendo; `dividendYield` y `netExpenseRatio` vienen en %;
  ADRs con `financialCurrency` ≠ `currency` mezclan monedas; yfinance 1.x devuelve MultiIndex. Detalle en
  `CONTEXTO.md` §5.
- Retornos **semanales** para covarianza y correlación; los gemelos se sacan antes de recortar la ventana.
- El backtest y el análisis de hoy comparten `estrategias.armar_portafolios`: un cambio de lógica va ahí.
- Antes de commitear: `python -m pytest` (57 OK) y `python scripts/probar_local.py --rapido`. Si cambia un
  notebook, regenerar y ejecutarlo con nbconvert en `_local_run/` (ver `ESTADO.md` §5).
- Cifras citadas (README "Corrida de ejemplo", `CONTEXTO.md` §4, `ESTADO.md` §3) = las de
  `data/ejemplo_registro/`. Si se regenera, actualizar las tres.

## Cierre de sesión
Actualizar `ESTADO.md` (fecha, qué cambió, verificación, próximos pasos), `.claude/memory/project.md` y
`CHANGELOG.md` si hay versión nueva. Commit + push si el usuario lo pidió (si el push pide credenciales, lo hace
el usuario: Claude no ingresa tokens).
