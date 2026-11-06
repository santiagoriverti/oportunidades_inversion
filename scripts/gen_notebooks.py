"""Genera los notebooks de notebooks/ (no editarlos a mano: editar este script y regenerar).

Uso:  python scripts/gen_notebooks.py
El test tests/test_notebooks.py verifica que los .ipynb del repo sean exactamente los que genera este script.
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
REPO = "santiagoriverti/oportunidades_inversion"
NB01 = "01_oportunidades_y_portafolios.ipynb"
NB02 = "02_seguimiento_expost.ipynb"


def badge(nombre: str) -> str:
    url = f"https://colab.research.google.com/github/{REPO}/blob/main/notebooks/{nombre}"
    return f"[![Abrir en Colab](https://colab.research.google.com/assets/colab-badge.svg)]({url})"


SETUP = r'''# Configuración: en Colab clona (o actualiza) el repo e instala la última yfinance; en la PC usa la carpeta del repo
import os, sys, subprocess, importlib
REPO = 'https://github.com/santiagoriverti/oportunidades_inversion.git'
if 'google.colab' in sys.modules:
    RAIZ = '/content/oportunidades_inversion'
    if os.path.exists(RAIZ):
        # Trae la última versión de GitHub y descarta cambios locales (la copia de Colab es descartable)
        subprocess.run(['git', '-C', RAIZ, 'fetch', '-q', '--depth', '1', 'origin', 'main'], check=True)
        subprocess.run(['git', '-C', RAIZ, 'reset', '-q', '--hard', 'FETCH_HEAD'], check=True)
    else:
        subprocess.run(['git', 'clone', '-q', '--depth', '1', REPO, RAIZ], check=True)
    # Yahoo cambia seguido: la última yfinance suele ser la que funciona
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-U', 'yfinance'], check=True)
else:  # subir desde la carpeta actual hasta encontrar el repo
    RAIZ = os.getcwd()
    while not os.path.exists(os.path.join(RAIZ, 'src', 'pipeline.py')) and os.path.dirname(RAIZ) != RAIZ:
        RAIZ = os.path.dirname(RAIZ)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)
# Si el notebook ya se corrió en esta sesión, olvidar los módulos de src cargados (pueden ser viejos)
for m in [m for m in sys.modules if m == 'src' or m.startswith('src.')]:
    del sys.modules[m]
importlib.invalidate_caches()
v = subprocess.run(['git', '-C', RAIZ, 'log', '-1', '--format=%h (%ad) %s', '--date=short'],
                   capture_output=True, text=True).stdout.strip()
print('Versión del repo:', v or 'sin git')

import warnings
warnings.filterwarnings('ignore', category=FutureWarning)
import pandas as pd
from IPython.display import display, Markdown
from src.config import Config
from src.pipeline import Analisis
from src.portafolios import NOMBRES
from src import tablas, graficos, registro, expost, datos
pd.set_option('display.max_columns', 40)
pd.set_option('display.width', 200)'''

AVISO = ("> ⚠️ **Herramienta educativa y de análisis cuantitativo. No es asesoramiento financiero ni una "
         "recomendación de compra o venta.** Que un activo esté \"barato\" contra su historia no garantiza que "
         "vaya a subir, y los rendimientos pasados no garantizan rendimientos futuros.")


def md(texto: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": texto.strip("\n").splitlines(keepends=True)}


def code(texto: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": texto.strip("\n").splitlines(keepends=True)}


def notebook(celdas: list[dict]) -> dict:
    for i, c in enumerate(celdas):
        c["id"] = f"c{i:02d}"
    return {"cells": celdas, "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"}, "colab": {"provenance": [], "toc_visible": True}},
        "nbformat": 4, "nbformat_minor": 5}


# ------------------------------------------------------------------------------------------------ notebook 01
CELDAS_01 = [
    md(f"""
# Oportunidades de inversión: activos artificialmente bajos y portafolios óptimos

{badge(NB01)}

Sobre una lista de tickers que elegís vos, este notebook:

1. **Detecta qué activos están artificialmente bajos**: debajo de sus medias, de su tendencia y de su rango
   habitual, sobrevendidos, castigados contra el mercado y, para acciones, baratos según sus fundamentales
   (P/E contra su sector, PEG, flujo de caja, precio objetivo de los analistas).
2. **Arma 8 portafolios** que buscan el mejor retorno para cada nivel de riesgo (Markowitz, máximo Sharpe,
   mínima varianza, paridad de riesgo, HRP, Black-Litterman con las señales...) y te dice **qué comprar** con tu
   capital, en acciones/ETFs de EE.UU. o en **CEDEARs**.
3. **Prueba las estrategias en el pasado** (backtest) y **registra la corrida** en tu Google Drive para medir
   después cómo le fue de verdad (notebook 02).

**Cómo usarlo:** editá la celda de configuración (paso 1) y después *Entorno de ejecución → Ejecutar todas*.
Tarda 2 a 3 minutos con la lista por defecto (81 activos). Al final se descarga un ZIP con un Excel y un reporte
con todos los gráficos. Metodología completa: [docs/METODOLOGIA.md](https://github.com/{REPO}/blob/main/docs/METODOLOGIA.md).

{AVISO}
"""),
    code(SETUP),
    md("""
## 1. Configuración

Lo único que hace falta tocar. Los tickers son los de **Yahoo Finance**: acciones y ETFs de EE.UU. tal cual
(`AAPL`, `SPY`), cripto con `-USD` (`BTC-USD`) y otras bolsas con su sufijo (`SAP.DE`, `IUIT.L`). Algunos
alias se corrigen solos (`BRKB` → `BRK-B`, `BTC` → `BTC-USD`). Todo se convierte a **dólares**.

Con `TICKERS = None` se usa la lista por defecto ([data/universo.csv](https://github.com/santiagoriverti/oportunidades_inversion/blob/main/data/universo.csv)),
que también dice qué tickers de la lista original se corrigieron o excluyeron y por qué.
"""),
    code(r'''# ============================ 1. CONFIGURACIÓN (editá esta celda) ============================
# None = lista por defecto (81 activos). O tu propia lista, por ejemplo:
# TICKERS = ["AAPL", "MSFT", "NVDA", "GOOG", "GLD", "IEF", "BTC-USD", "SPY", "EWZ", "VALE"]
TICKERS = None

HORIZONTE = "mediano"         # "corto" (1-3 meses), "mediano" (6-12 meses) o "largo" (3+ años)
CAPITAL_USD = 10_000          # plata a invertir, para calcular cuánto comprar de cada activo
PESO_MAXIMO = 0.20            # tope por activo en cada portafolio (0.20 = 20%)
VOLATILIDAD_OBJETIVO = 0.10   # volatilidad anual buscada en el portafolio "Volatilidad objetivo"
INCLUIR_FUNDAMENTALES = True  # P/E, PEG, flujo de caja, precio objetivo de analistas (suma ~30 segundos)
CORRER_BACKTEST = True        # backtest walk-forward de todas las estrategias (~30 segundos)
GUARDAR_EN_DRIVE = True       # registra la corrida en Google Drive para el seguimiento (notebook 02)

cfg = Config.desde_horizonte(HORIZONTE, tickers=TICKERS, capital_usd=CAPITAL_USD, peso_maximo=PESO_MAXIMO,
                             volatilidad_objetivo=VOLATILIDAD_OBJETIVO, incluir_fundamentales=INCLUIR_FUNDAMENTALES,
                             correr_backtest=CORRER_BACKTEST, guardar_registro=GUARDAR_EN_DRIVE)
print(f"Horizonte {cfg.horizonte}: ventana de {cfg.ventana_anios:g} años, rebalanceo {cfg.rebalanceo}, "
      f"pesos del score {cfg.pesos_grupos}")'''),
    code(r'''A = Analisis(cfg).cargar_datos()
fuera = A.universo[A.universo["estado_analisis"] != "analizado"]
if len(fuera):
    display(Markdown("**Tickers que no se analizan** (y por qué):"))
    display(fuera[["ticker", "yahoo", "estado_analisis", "nota"]].set_index("ticker"))'''),
    md("""
## 2. ¿Qué está artificialmente bajo?

Para cada activo se calculan métricas en tres grupos y cada una se pasa a **percentil dentro de tu lista**
(100 = el más "barato"):

| Grupo | Métricas |
|---|---|
| **Técnico** | precio vs media de 50 y de 200 días, ubicación en el rango de 52 semanas, RSI de 14 días, %B de Bollinger |
| **Estadístico** | z-score del precio contra su año, desvío contra su tendencia de 3 años, qué tan inusual es la caída de 3 meses, z-score contra el benchmark (SPY) |
| **Fundamental** (solo acciones) | upside del precio objetivo de los analistas, P/E contra el ETF de su sector, PEG, rendimiento del flujo de caja libre |

El **score** (0-100) promedia los grupos con los pesos del horizonte. Como el score es *relativo* a la lista,
además se cuentan las **señales absolutas** (por ejemplo: precio debajo de su media de 200 días, RSI ≤ 30, caída
de 25% o más desde el máximo de 52 semanas, upside de analistas ≥ 20%).

- **Oportunidad**: score ≥ 70 y al menos 2 señales absolutas.
- **Oportunidad con alertas**: lo mismo, pero con una alerta: *cuchillo que cae* (−15% en un mes y tendencia
  bajista), *posible trampa de valor* (el mercado espera menores ganancias) o precio por encima del objetivo
  de los analistas. Mirarlas con más cuidado: lo barato puede seguir abaratándose.
- **Vigilar**, **Neutral**, **Sobreextendida** (score ≤ 30: está caro contra su propia historia).
"""),
    code(r'''A.calcular_senales()
display(Markdown("### Oportunidades detectadas"))
display(tablas.estilo_senales(A.senales, n=None, solo=["Oportunidad", "Oportunidad con alertas"]))'''),
    code(r'''nombres = dict(zip(A.senales.index, A.senales["nombre"]))
graficos.fig_ranking(A.senales, 30, nombres).show()
graficos.fig_mapa_senales(A.senales, 25).show()'''),
    md("""
Precio de las oportunidades con sus medias de 50 y 200 días y las bandas de Bollinger (elegí el activo en el
menú de arriba a la derecha):
"""),
    code(r'''from src.senales import top_oportunidades
graficos.fig_precios(A.precios, top_oportunidades(A.senales, 10)).show()'''),
    code(r'''display(Markdown("### Todos los activos (ordenados por score)"))
display(tablas.estilo_senales(A.senales, n=None))'''),
    code(r'''if A.fundamentales is not None:
    display(Markdown("### Fundamentales de las acciones (foto actual de Yahoo Finance)"))
    cols = ["sector", "pe_trailing", "pe_forward", "pe_relativo_sector", "peg", "fcf_yield", "rend_dividendo",
            "upside_analistas", "recomendacion", "n_analistas", "monedas_mezcladas"]
    f = A.fundamentales[A.fundamentales["tipo_yahoo"] == "EQUITY"][cols].sort_values("pe_relativo_sector")
    display(tablas.estilo_porcentajes(f, pct=["fcf_yield", "rend_dividendo", "upside_analistas"],
                                      dec={"pe_trailing": "{:.1f}", "pe_forward": "{:.1f}",
                                           "pe_relativo_sector": "{:.2f}", "peg": "{:.2f}",
                                           "recomendacion": "{:.1f}", "n_analistas": "{:.0f}"}))'''),
    md("""
## 3. Riesgo y retorno histórico

Métricas de cada activo en la ventana del horizonte (3 años en "mediano"): retorno anual compuesto,
volatilidad, **Sharpe** y **Sortino** (retorno extra sobre la tasa libre de riesgo por unidad de riesgo total o
de caída), **máxima caída**, **Calmar**, **VaR y CVaR** diarios al 95%, y **beta/alfa** contra el benchmark
(con retornos semanales, porque BTC y los ETFs europeos no cotizan en el mismo horario que EE.UU.).
"""),
    code(r'''display(tablas.estilo_metricas(A.metricas.sort_values("sharpe", ascending=False)))'''),
    md("""
## 4. Portafolios sugeridos

Todos **sin ventas en corto**, con un **tope por activo** y con la covarianza estimada con retornos semanales y
contracción de **Ledoit-Wolf** (más estable). Los activos casi idénticos (*gemelos*: SPY/VOO/VTI, GLD/IAU,
QQQ/QQQM...) se optimizan como uno solo y se indican sus equivalentes.

| Portafolio | Idea |
|---|---|
| **Pesos iguales (1/N)** | referencia ingenua y difícil de vencer |
| **Mínima varianza** | el menor riesgo posible (no usa retornos esperados) |
| **Máximo Sharpe (Markowitz)** | el portafolio tangente: máximo retorno por unidad de riesgo |
| **Volatilidad objetivo** | máximo retorno con la volatilidad elegida en la configuración |
| **Paridad de riesgo** | cada activo aporta el mismo riesgo |
| **HRP (López de Prado)** | agrupa activos parecidos y reparte el riesgo por grupos; robusto a errores de estimación |
| **Black-Litterman con señales** | parte del equilibrio y lo inclina hacia los activos con mejor score de oportunidad |
| **Oportunidades** | las mejores oportunidades del paso 2, con paridad de riesgo |

> **Ojo con los retornos esperados:** Markowitz, máximo Sharpe y volatilidad objetivo usan el retorno
> histórico de la ventana, que premia a los que *ya* subieron mucho. Por eso el resumen muestra también la
> versión histórica de cada portafolio, y conviene mirar los robustos (mínima varianza, paridad de riesgo, HRP) y
> el backtest del paso 6 antes de decidir.
"""),
    code(r'''A.optimizar()
display(Markdown("### Resumen (ex-ante con el modelo; *_hist* = cómo le fue en la ventana con esos pesos)"))
display(tablas.estilo_resumen_portafolios(A.resumen.drop(columns=["clave"])))
if len(A.tabla_gemelos):
    display(Markdown("### Gemelos: se optimiza con el primero; los otros son equivalentes"))
    display(A.tabla_gemelos)
display(Markdown("### Activos que quedaron fuera de la optimización"))
display(A.excluidos_opt)'''),
    code(r'''res = A.portafolios
graficos.fig_frontera(res["frontera"], res["mu"], res["cov"], A.pesos, A.rf).show()
graficos.fig_pesos(A.pesos).show()
graficos.fig_contribucion_riesgo(A.pesos, res["cov"]).show()'''),
    code(r'''from src.portafolios import orden_hrp
graficos.fig_correlaciones(res["cov"], orden_hrp(res["cov"])).show()'''),
    md("""
## 5. Qué comprar

Cantidades para el `CAPITAL_USD` de la configuración, en dos versiones:

- **EE.UU.**: acciones y ETFs originales al último precio (las cripto se compran fraccionadas).
- **CEDEARs**: especie D (dólar MEP) de BYMA con el precio en vivo de [data912](https://data912.com); si un CEDEAR
  solo cotiza en pesos, se pasa a dólares con el **MEP implícito**. Lo que no tiene CEDEAR se marca para comprar
  afuera.

Se compran unidades enteras: primero la parte entera de cada posición y después, con lo que sobra, la posición
más lejos de su objetivo. Elegí el portafolio en la celda de abajo.
"""),
    code(r'''A.asignar()
# Elegí uno: pesos_iguales, minima_varianza, maximo_sharpe, volatilidad_objetivo, paridad_riesgo, hrp,
#            black_litterman, oportunidades
PORTAFOLIO = "maximo_sharpe"

t, sobrante = A.tabla_compra(PORTAFOLIO, "usd")
display(Markdown(f"### {NOMBRES[PORTAFOLIO]} — en EE.UU. (sobran USD {sobrante:,.2f})"))
display(tablas.estilo_asignacion(t[t["peso_objetivo"] > 0]))
if "cedear" in A.asignaciones[PORTAFOLIO]:
    t2, sobrante2 = A.tabla_compra(PORTAFOLIO, "cedear")
    display(Markdown(f"### {NOMBRES[PORTAFOLIO]} — con CEDEARs (sobran USD {sobrante2:,.2f}; "
                     f"MEP implícito {A.mep:,.0f})" if A.mep else f"### {NOMBRES[PORTAFOLIO]} — con CEDEARs"))
    display(tablas.estilo_asignacion(t2))'''),
    md("""
## 6. Backtest: ¿cómo les hubiera ido a las estrategias?

**Walk-forward**: en cada fin de trimestre (en el horizonte "mediano") se recalculan las señales y los
portafolios **solo con los datos disponibles hasta ese día**, se mantienen hasta el próximo rebalanceo y se
descuenta un costo por rotación. Además se mide si el **score anticipó** los retornos del trimestre siguiente
(IC de Spearman: 0 = nada, positivo = los de score alto rindieron más).

> **Sesgos a tener en cuenta:** la lista de tickers se eligió hoy (no están los que quebraron o se dejaron de
> mirar: *sesgo de supervivencia*), y el score del backtest no usa fundamentales (Yahoo no da su historia).
> Tomalo como una referencia de comportamiento, no como una promesa.
"""),
    code(r'''if cfg.correr_backtest:
    A.correr_backtest()
    display(tablas.estilo_backtest(A.backtest["metricas"]))
    graficos.fig_backtest(A.backtest["retornos"], A.benchmark).show()
    ic = A.resumen_ic
    if ic:
        display(Markdown(
            f"**Capacidad predictiva del score** en {ic['periodos']} rebalanceos: IC medio **{ic['ic_medio']:+.3f}** "
            f"(t = {ic['ic_t_stat']:.2f}; positivo en {ic['pct_ic_positivo']:.0%} de los períodos). Las oportunidades "
            f"rindieron en promedio **{ic['exceso_medio_oportunidades']:+.1%}** por período contra el promedio de la "
            f"lista y le ganaron en {ic['pct_periodos_oportunidades_ganan']:.0%} de los períodos. "
            "Un |t| menor a 2 quiere decir que no se distingue del azar."))
        graficos.fig_ic(A.backtest["ic"]).show()
else:
    print("Backtest desactivado en la configuración (CORRER_BACKTEST = False).")'''),
    md("""
## 7. Guardar la corrida (para el seguimiento ex-post)

Se guarda en **Google Drive**, en `Mi unidad/oportunidades_inversion/registros/AAAAMMDD_HHMMSS/` (la primera vez
Colab pide permiso para acceder al Drive). Ahí quedan las señales, los pesos de los 8 portafolios, las cantidades a
comprar y los precios del día. El **notebook 02** lee todas las corridas y mide cuánto rindió cada estrategia.
"""),
    code(r'''if cfg.guardar_registro:
    A.guardar()
else:
    print("No se guarda la corrida (GUARDAR_EN_DRIVE = False).")'''),
    md(f"""
## 8. Descargar todo

ZIP con el **Excel** (una hoja por tabla), el **reporte HTML** con todos los gráficos interactivos (se abre sin
internet) y la carpeta de la corrida. En Colab se descarga solo.

Para ver cómo les fue a las corridas guardadas: {badge(NB02)}
"""),
    code(r'''zip_path = A.exportar()
if A.avisos:
    display(Markdown("**Avisos de esta corrida:**\n" + "\n".join(f"- {a}" for a in A.avisos)))'''),
]

# ------------------------------------------------------------------------------------------------ notebook 02
CELDAS_02 = [
    md(f"""
# Seguimiento ex-post: ¿cómo les fue a las corridas guardadas?

{badge(NB02)}

Lee las corridas que guardó el notebook 01 en tu Google Drive (`Mi unidad/oportunidades_inversion/registros`) y,
con precios **actuales**, mide para cada una:

- cuánto rindió cada uno de los 8 portafolios desde la fecha de la corrida (comprando ese día y manteniendo),
  contra el benchmark (SPY), en total y a 1, 3, 6 y 12 meses;
- si las **señales** acertaron: cuánto rindieron las "Oportunidades" contra el resto y la correlación entre el
  score y el retorno posterior;
- un **ranking de estrategias** con todas las corridas juntas.

Si todavía no tenés corridas propias se usa la **corrida de ejemplo** del repo (lista por defecto, 06/11/2026).
Retorno anualizado, volatilidad y Sharpe aparecen recién con 3 meses de historia (con menos no significan nada).

{AVISO}
"""),
    code(SETUP),
    code(r'''# ============================ CONFIGURACIÓN ============================
CARPETA = None          # None = Google Drive (Mi unidad/oportunidades_inversion/registros); o una ruta propia
INCLUIR_EJEMPLO = True  # suma la corrida de ejemplo del repo (data/ejemplo_registro)
BENCHMARK = "SPY"

carpeta = CARPETA or registro.carpeta_por_defecto()
lista = registro.listar_corridas(carpeta)
print(f"Corridas propias en {carpeta}: {len(lista)}")
rutas = list(lista["ruta"])
if INCLUIR_EJEMPLO or not rutas:
    ejemplo = registro.listar_corridas(os.path.join(RAIZ, "data", "ejemplo_registro"))
    rutas += [r for r in ejemplo["ruta"] if r not in rutas]
    lista = pd.concat([lista, ejemplo.assign(run_id=ejemplo["run_id"] + " (ejemplo)")], ignore_index=True)
display(lista.drop(columns=["ruta"]))
corridas = [registro.cargar_corrida(r) for r in rutas]'''),
    code(r'''R = None
if corridas:
    precios, avisos = expost.descargar_precios_corridas(corridas, BENCHMARK)
    for a in avisos:
        print("aviso:", a)
    rf = datos.tasa_libre_riesgo()[0]
    R = expost.evaluar_todas(corridas, precios, BENCHMARK, rf)
    print(f"Precios hasta el {precios.index.max().date()}; tasa libre de riesgo {rf:.2%}.")
else:
    print("No hay corridas para evaluar: corré primero el notebook 01 con GUARDAR_EN_DRIVE = True.")'''),
    md("""
## Ranking de estrategias (todas las corridas)

`exceso_medio` = retorno del portafolio menos el del benchmark en el mismo período, promediado entre corridas;
`pct_le_gana_al_benchmark` = en qué fracción de las corridas le ganó.
"""),
    code(r'''if R is not None and len(R["ranking"]):
    display(tablas.estilo_expost(R["ranking"]))
    graficos.fig_ranking_expost(R["ranking"]).show()
    display(Markdown("### ¿Acertaron las señales?"))
    display(tablas.estilo_porcentajes(R["senales"], pct=["pct_oportunidades_ganan", "retorno_benchmark"],
                                      dec={"ic_score_vs_retorno": "{:+.2f}", "dias": "{:.0f}"}))'''),
    md("""
## Detalle de una corrida

Por defecto la más reciente (`CORRIDA = -1`); `0` es la más vieja.
"""),
    code(r'''CORRIDA = -1
if R is not None and R["evaluaciones"]:
    e = R["evaluaciones"][CORRIDA]
    display(Markdown(f"### Corrida {e['run_id']}: datos al {e['fecha_datos'].date()} ({e['dias']} días hábiles)"))
    display(tablas.estilo_expost(e["tabla"].drop(columns=["clave"])))
    graficos.fig_curvas_expost(e["curvas"], f"Corrida {e['run_id']}: valor de 1 USD invertido").show()
    display(Markdown("**Retorno posterior por clasificación de la corrida:**"))
    display(tablas.estilo_porcentajes(e["por_clase"], pct=["retorno_medio", "retorno_mediano"]))
    graficos.fig_score_vs_retorno(e["senales"], e["retorno_benchmark"]).show()
    for a in e["avisos"]:
        print("aviso:", a)'''),
    md("""
## Descargar el seguimiento

ZIP con el Excel (ranking, todas las corridas, señales) y el reporte HTML con los gráficos.
"""),
    code(r'''if R is not None:
    expost.exportar_seguimiento(R)'''),
]


def generar() -> dict[str, dict]:
    return {NB01: notebook(CELDAS_01), NB02: notebook(CELDAS_02)}


def serializar(nb: dict) -> str:
    return json.dumps(nb, ensure_ascii=False, indent=1) + "\n"


def main() -> None:
    carpeta = RAIZ / "notebooks"
    carpeta.mkdir(exist_ok=True)
    for nombre, nb in generar().items():
        (carpeta / nombre).write_text(serializar(nb), encoding="utf-8", newline="\n")
        print("escrito", f"notebooks/{nombre}")


if __name__ == "__main__":
    main()
