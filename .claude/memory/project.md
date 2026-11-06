# Memoria del proyecto oportunidades_inversion

## Sesión 1 — 2026-11-06 (una sola sesión larga, cortada una vez por el límite de uso)

**Pedido**: notebook de Colab desde el README para (1) detectar activos artificialmente bajos sobre una lista de
tickers del usuario, (2) sugerir portafolios Markowitz/Sharpe/etc. comprables y (3) registrar todo para medir
ex-post. Lista original de 87 tickers (incluye bonos/ONs de BYMA y comentarios de quien se los recomendó).

**Preguntas y respuestas** (todas las recomendadas): registro en Google Drive; AO28/HJCLO/NPCDO/YMCXO excluidos
(sin historia gratis; renta fija → roadmap); asignación en EE.UU. y CEDEARs; horizonte mediano.

**Hallazgos al validar los tickers** (yfinance 1.8): `UN` es otro ETF (jul-2026); `VGII` no existe (→ VGIT);
`XE` = X-energy desde 2026-04-24; OKLO y SMR traen la historia de su SPAC; EXX1/QDVE/VVSM cotizan en EUR en Xetra;
data912 tiene cotización en vivo de los bonos/ONs pero no historia. Correlación diaria vs semanal con Xetra/BTC
muy distinta → covarianza semanal.

**Construido**: `src/` (18 módulos, clase `Analisis`), `data/universo.csv`, `scripts/probar_local.py`,
`scripts/gen_notebooks.py`, notebooks 01 y 02, corrida de ejemplo `data/ejemplo_registro/20261106_204148`,
57 tests + CI, README, CONTEXTO, ESTADO, CLAUDE, docs/METODOLOGIA, ARQUITECTURA, ROADMAP, CHANGELOG.

**Errores encontrados y corregidos en el camino**: ventana acortada por un gemelo joven (IBIT); representante de
gemelos por orden alfabético (ahora benchmark → patrimonio → lista); VALE con 49% de dividendo (monedas
mezcladas); Sharpe de 10¹⁶ con volatilidad ~0; media vida de 10¹⁷ días; `.gitignore` con comentarios en línea
(git no los admite); ruta absoluta de la PC en el metadata; gráficos: título pisado por la leyenda, etiquetas
encimadas en la frontera, fila "otros" aplastando la escala de pesos.

**Verificación**: análisis completo local ~60 s; notebooks 01 y 02 ejecutados con nbconvert sin errores;
reporte HTML revisado en el navegador integrado; 57 tests OK. **Falta**: correrlos en Colab con la cuenta del
usuario.

**Resultado clave**: el score de oportunidad NO predijo retornos trimestrales en el backtest (IC +0,003, t 0,05).
