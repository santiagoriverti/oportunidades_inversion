"""Orquestación del análisis completo: clase ``Analisis`` (la usan los notebooks y scripts/probar_local.py).

    A = Analisis(Config.desde_horizonte("mediano"))
    A.cargar_datos()        # precios en USD, calidad, tasa libre de riesgo
    A.calcular_senales()    # indicadores, fundamentales, score de oportunidad, métricas de riesgo
    A.optimizar()           # 8 portafolios + frontera eficiente
    A.asignar()             # cantidades a comprar (EE.UU. y CEDEARs)
    A.correr_backtest()     # walk-forward de las estrategias
    A.guardar()             # registro de la corrida (Drive en Colab)
    A.exportar()            # Excel + reporte HTML + ZIP

Cada paso se puede volver a correr después de cambiar ``A.cfg`` (por ejemplo, otro peso máximo) sin volver a
bajar los datos.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import (__version__, asignacion, backtest, datos, estrategias, exportar, fundamentales, graficos,
               indicadores, metricas, portafolios, registro, senales, universo)
from .config import RAIZ, Config
from .portafolios import NOMBRES

AVISO_LEGAL = ("Herramienta educativa y de análisis cuantitativo. No es asesoramiento financiero ni una "
               "recomendación de compra o venta. Rendimientos pasados no garantizan rendimientos futuros.")


class Analisis:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self.cfg.validar()
        self.avisos: list[str] = []
        self.ruta_registro = None
        self.backtest = None
        self.resumen_ic: dict = {}
        self.mep = None
        self.tabla_cedears = None
        self.fundamentales = None

    def _aviso(self, msg: str) -> None:
        self.avisos.append(msg)
        print(f"  aviso: {msg}")

    def _rf_medio(self, inicio, fin=None) -> float:
        """Tasa libre de riesgo promedio de un período (para Sharpe histórico); la actual si no hay serie."""
        s = getattr(self, "rf_serie", None)
        if s is None or s.empty:
            return self.rf
        s = s.loc[pd.Timestamp(inicio): (pd.Timestamp(fin) if fin is not None else None)]
        return float(s.mean()) if len(s) else self.rf

    # ------------------------------------------------------------------------------------------- 1. datos
    def cargar_datos(self) -> "Analisis":
        cfg = self.cfg
        t0 = time.time()
        u = universo.resolver_universo(cfg.tickers, cfg.ruta_universo)
        self.benchmark = universo.normalizar_ticker(cfg.benchmark)
        act, ref = universo.activos(u), universo.referencias(u)
        simbolos = list(dict.fromkeys(act + ref + [self.benchmark]))
        inicio = pd.Timestamp.today().normalize() - pd.Timedelta(days=int(cfg.anios_historia * 365.25) + 10)
        print(f"Descargando {len(simbolos)} símbolos de Yahoo Finance desde {inicio.date()}...")
        crudos, faltan = datos.descargar_cierres(simbolos, inicio)
        if faltan:
            self._aviso(f"Yahoo no devolvió datos para: {', '.join(faltan)}")
        if self.benchmark not in crudos.columns:
            raise RuntimeError(f"No hay datos del benchmark {self.benchmark}: no se puede seguir")
        fecha_datos = crudos[self.benchmark].dropna().index.max()
        crudos = crudos.loc[:fecha_datos]
        p = datos.alinear_dias_habiles(crudos)
        inicios = {s: f for s, f in universo.mapa(u, "inicio_valido").items() if f}
        p = datos.aplicar_inicio_valido(p, inicios)
        self.monedas = datos.detectar_monedas(list(p.columns), universo.mapa(u, "moneda"))
        p, av = datos.convertir_a_usd(p, self.monedas, inicio)
        for a in av:
            self._aviso(a)
        sin_datos = [s for s in act if s not in p.columns or p[s].dropna().empty]
        if sin_datos:
            self._aviso(f"Sin precios válidos (quedan fuera): {', '.join(sin_datos)}")
        self.activos = [s for s in act if s not in sin_datos]
        self.referencias = [s for s in ref if s in p.columns and not p[s].dropna().empty]
        self.sin_datos = sin_datos
        estado = []
        for r in u.itertuples(index=False):
            if r.estado == "excluido":
                estado.append("excluido del análisis")
            elif r.yahoo in sin_datos:
                estado.append("sin datos de Yahoo")
            elif r.estado == "referencia":
                estado.append("referencia (no invertible)")
            else:
                estado.append("analizado")
        u = u.assign(estado_analisis=estado)
        self.universo, self.crudos, self.precios, self.fecha_datos = u, crudos, p, fecha_datos
        self.inicio_ventana = fecha_datos - pd.Timedelta(days=int(round(cfg.ventana_anios * 365.25)))
        self.calidad = datos.reporte_calidad(crudos, p, self.inicio_ventana, fecha_datos)
        viejos = self.calidad.index[self.calidad.get("dias_sin_dato", pd.Series(dtype=float)) > 5].tolist()
        if viejos:
            self._aviso(f"Más de 5 días hábiles sin cotizar: {', '.join(viejos)}")
        if cfg.tasa_libre_riesgo is not None:
            self.rf, self.rf_serie, self.rf_fuente = float(cfg.tasa_libre_riesgo), pd.Series(dtype=float), "fijada a mano"
        else:
            self.rf, self.rf_serie, self.rf_fuente = datos.tasa_libre_riesgo(inicio)
        print(f"OK en {time.time() - t0:.0f}s: {len(self.activos)} activos con datos"
              f"{f', {len(self.referencias)} de referencia' if self.referencias else ''}; precios al "
              f"{fecha_datos.date()}; tasa libre de riesgo {self.rf:.2%} ({self.rf_fuente}).")
        return self

    # ------------------------------------------------------------------------------------------- 2. señales
    def calcular_senales(self) -> "Analisis":
        cfg, act, bench = self.cfg, self.activos, self.benchmark
        t0 = time.time()
        cols = list(dict.fromkeys(act + [bench]))
        self.paneles = indicadores.panel_indicadores(self.precios[cols], bench)
        f = indicadores.foto(self.paneles, self.fecha_datos).loc[act]
        f = f.join(indicadores.reversion_media(self.precios[act]))
        if cfg.incluir_fundamentales:
            print(f"Bajando fundamentales de {len(act)} activos (Yahoo, ~1 minuto)...")
            self.fundamentales, av = fundamentales.obtener_fundamentales(act)
            for a in av:
                self._aviso(a)
        else:
            self.fundamentales = None
        tabla = senales.calcular_score(f, self.fundamentales, cfg.pesos_grupos, cfg.umbrales_senales,
                                       cfg.umbral_score_oportunidad, cfg.min_senales_oportunidad)
        info = self.universo[self.universo["yahoo"] != ""].set_index("yahoo")
        fund = self.fundamentales if self.fundamentales is not None else pd.DataFrame()

        def dato(s, col, col_fund=None):
            v = info.at[s, col] if s in info.index else ""
            if (not v or v == s) and col_fund and s in fund.index:
                v = fund.at[s, col_fund]
                if col == "tipo":
                    v = universo.TIPO_POR_QUOTETYPE.get(str(v).upper(), "")
            return v or ""

        tabla.insert(0, "nombre", [dato(s, "nombre", "nombre_yahoo") for s in tabla.index])
        tabla.insert(1, "tipo", [dato(s, "tipo", "tipo_yahoo") for s in tabla.index])
        tabla.insert(2, "rubro", [dato(s, "rubro") for s in tabla.index])
        self.senales = tabla
        self.preferencia = self._orden_preferencia()
        self.metricas = metricas.tabla_metricas_activos(self.precios[cols], self.inicio_ventana,
                                                        self._rf_medio(self.inicio_ventana), bench)
        cuenta = tabla["clasificacion"].value_counts()
        print(f"OK en {time.time() - t0:.0f}s: " + ", ".join(f"{k}: {v}" for k, v in cuenta.items()))
        return self

    def _orden_preferencia(self) -> list[str]:
        """Orden para elegir el representante de un grupo de gemelos con la misma historia: primero el
        benchmark, después el de mayor tamaño (patrimonio del ETF o capitalización) y por último el orden de la
        lista del usuario."""
        tam = pd.Series(np.nan, index=self.activos)
        f = self.fundamentales
        if f is not None and not f.empty:
            for s in self.activos:
                if s in f.index:
                    v = f.at[s, "activos_etf"] if "activos_etf" in f.columns else np.nan
                    if not np.isfinite(v) and "market_cap" in f.columns:
                        v = f.at[s, "market_cap"]
                    tam[s] = v
        orden = {s: i for i, s in enumerate(self.activos)}
        return sorted(self.activos, key=lambda s: (s != self.benchmark,
                                                   -(tam[s] if np.isfinite(tam[s]) else -1.0), orden[s]))

    def _donde_comprar(self, activo: str, sin_cedear: bool = False) -> str:
        """Texto de dónde se compra un activo que no se compra como CEDEAR."""
        tipo = self.senales.at[activo, "tipo"] if activo in self.senales.index else ""
        moneda = self.monedas.get(activo, "USD")
        if tipo == "cripto":
            return "cripto: exchange o su ETF equivalente"
        if "." in activo or moneda.upper() != "USD":
            return f"{'sin CEDEAR: ' if sin_cedear else ''}en su bolsa de origen ({moneda}; precio pasado a USD)"
        return "sin CEDEAR: comprar en EE.UU." if sin_cedear else "acción/ETF en EE.UU."

    # ------------------------------------------------------------------------------------------- 3. portafolios
    def optimizar(self) -> "Analisis":
        cfg = self.cfg
        self.cfg.validar()
        t0 = time.time()
        self.top = senales.top_oportunidades(self.senales, cfg.top_n_oportunidades)
        res = estrategias.armar_portafolios(self.precios, self.activos, cfg, self.rf, score=self.senales["score"],
                                            top=self.top, benchmark=self.benchmark, preferencia=self.preferencia,
                                            calcular_frontera=True)
        self.portafolios = res
        self.pesos = {k: w for k, w in res["pesos"].items() if w is not None}
        tabla = portafolios.resumen(self.pesos, res["mu"], res["cov"], self.rf)
        ini, fin, _ = res["ventana"]
        if ini is not None and not tabla.empty:
            rd = self.precios.loc[ini:fin].pct_change(fill_method=None).iloc[1:]
            rf_h = self._rf_medio(ini, fin)
            for nombre in tabla.index:
                w = self.pesos[tabla.at[nombre, "clave"]]
                r = (rd[w.index].fillna(0.0) * w.to_numpy()).sum(axis=1)
                m = metricas.resumen_serie(r, rf_h)
                tabla.loc[nombre, "retorno_hist"] = m["retorno_anual"]
                tabla.loc[nombre, "volatilidad_hist"] = m["volatilidad"]
                tabla.loc[nombre, "sharpe_hist"] = m["sharpe"]
                tabla.loc[nombre, "max_drawdown_hist"] = m["max_drawdown"]
        self.resumen = tabla
        self.tabla_gemelos = self._tabla_gemelos(res["gemelos"])
        self.excluidos_opt = pd.DataFrame({"motivo": pd.Series(res["excluidos"], dtype=object)})
        self.excluidos_opt.index.name = "activo"
        v = res["ventana"]
        print(f"OK en {time.time() - t0:.0f}s: {len(res['cov'])} activos optimizables, ventana "
              f"{v[0].date() if v[0] is not None else '-'} a {v[1].date() if v[1] is not None else '-'} "
              f"({v[2]} días), contracción Ledoit-Wolf {res['shrinkage']:.2f}.")
        for k, n in res["notas"].items():
            print(f"  nota {NOMBRES.get(k, k)}: {n}")
        return self

    def _tabla_gemelos(self, gemelos: list[list[str]]) -> pd.DataFrame:
        gasto = (self.fundamentales["gasto_anual_etf"] if self.fundamentales is not None
                 and "gasto_anual_etf" in self.fundamentales.columns else pd.Series(dtype=float))
        filas = []
        for g in gemelos:
            gastos = {s: float(gasto.get(s, np.nan)) for s in g}
            validos = {s: v for s, v in gastos.items() if np.isfinite(v)}
            # "más barato" solo si se pueden comparar (el representante y al menos otro con gasto conocido):
            # BTC-USD no tiene gasto de fondo, no tiene sentido decir que IBIT es más barato
            comparable = len(validos) >= 2 and g[0] in validos
            filas.append({
                "representante": g[0],
                "equivalentes": ", ".join(g[1:]),
                "mas_barato": min(validos, key=validos.get) if comparable else "",
                "gasto_anual": "; ".join(f"{s} {v:.2%}" for s, v in validos.items()),
            })
        return pd.DataFrame(filas, columns=["representante", "equivalentes", "mas_barato", "gasto_anual"])

    def _alternativas(self) -> dict[str, str]:
        """Activo representante -> texto con sus equivalentes (y el de menor costo)."""
        out = {}
        for r in self.tabla_gemelos.itertuples(index=False):
            texto = f"equivalentes: {r.equivalentes}"
            if r.mas_barato and r.mas_barato != r.representante:
                texto += f" (menor costo: {r.mas_barato})"
            out[r.representante] = texto
        return out

    # ------------------------------------------------------------------------------------------- 4. qué comprar
    def asignar(self) -> "Analisis":
        cfg = self.cfg
        self.precios_hoy = self.precios.loc[self.fecha_datos, self.activos].dropna()
        cripto = set(self.senales.index[self.senales["tipo"] == "cripto"])
        self.tabla_cedears = None
        if cfg.incluir_cedears:
            cot, self.mep, msg = datos.cotizaciones_cedears()
            print(msg)
            if cot is not None:
                t = asignacion.precios_cedears(universo.mapa_cedears(self.universo), cot, self.mep)
                self.tabla_cedears = asignacion.con_equivalentes(t, self.portafolios["gemelos"])
        alt = self._alternativas()
        self.asignaciones, partes = {}, []
        for k, w in self.pesos.items():
            t_usd, s_usd = asignacion.asignacion_discreta(w, self.precios_hoy, cfg.capital_usd,
                                                          cfg.permitir_fracciones, fraccionables=cripto)
            t_usd["vehiculo"] = [self._donde_comprar(s) for s in t_usd.index]
            t_usd["alternativas"] = [alt.get(s, "") for s in t_usd.index]
            entrada = {"usd": (t_usd, s_usd)}
            partes.append(t_usd.reset_index().assign(portafolio=k, opcion="EE.UU.", sobrante=s_usd))
            if self.tabla_cedears is not None and not self.tabla_cedears.empty:
                t_c, s_c = asignacion.asignacion_con_cedears(w, self.precios_hoy, self.tabla_cedears, cfg.capital_usd,
                                                             cfg.permitir_fracciones, fraccionables=cripto)
                sin = ~t_c["vehiculo"].str.startswith("CEDEAR")
                t_c.loc[sin, "vehiculo"] = [self._donde_comprar(s, sin_cedear=True) for s in t_c.index[sin]]
                entrada["cedear"] = (t_c, s_c)
                partes.append(t_c.reset_index().assign(portafolio=k, opcion="CEDEARs", sobrante=s_c))
            self.asignaciones[k] = entrada
        self.asignacion_larga = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
        print(f"OK: cantidades para {len(self.asignaciones)} portafolios con USD {cfg.capital_usd:,.0f}"
              + (" (EE.UU. y CEDEARs)." if self.tabla_cedears is not None else " (EE.UU.)."))
        return self

    def tabla_compra(self, clave: str, opcion: str = "usd") -> tuple[pd.DataFrame, float]:
        """Tabla de compra de un portafolio: opcion "usd" (EE.UU.) o "cedear"."""
        e = self.asignaciones.get(clave, {})
        if opcion not in e:
            raise KeyError(f"No hay asignación '{opcion}' para {clave}")
        return e[opcion]

    # ------------------------------------------------------------------------------------------- 5. backtest
    def correr_backtest(self) -> "Analisis":
        print(f"Backtest walk-forward (rebalanceo {self.cfg.rebalanceo}, ventana {self.cfg.ventana_anios:g} años)...")
        rf_bt = self._rf_medio(self.precios.index[0])
        self.backtest = backtest.correr_backtest(self.precios, self.activos, self.cfg, rf_bt, self.benchmark,
                                                 preferencia=self.preferencia)
        self.resumen_ic = backtest.resumen_ic(self.backtest["ic"])
        print(f"OK en {self.backtest['segundos']:.0f}s: {len(self.backtest['fechas'])} rebalanceos.")
        return self

    # ------------------------------------------------------------------------------------------- 6. registro
    def metadata(self) -> dict:
        res = self.portafolios
        v = res["ventana"]
        config = self.cfg.como_dict()
        try:  # ruta relativa al repo (no guardar rutas de la PC en el registro)
            config["ruta_universo"] = Path(config["ruta_universo"]).resolve().relative_to(RAIZ).as_posix()
        except ValueError:
            pass
        return {
            "fecha_datos": str(self.fecha_datos.date()),
            "benchmark": self.benchmark,
            "tasa_libre_riesgo": self.rf,
            "fuente_tasa": self.rf_fuente,
            "config": config,
            "tickers_pedidos": self.universo["ticker"].tolist(),
            "activos_analizados": self.activos,
            "referencias": self.referencias,
            "sin_datos": self.sin_datos,
            "excluidos_del_universo": self.universo.loc[self.universo["estado"] == "excluido", "ticker"].tolist(),
            "excluidos_optimizacion": res["excluidos"],
            "gemelos": res["gemelos"],
            "ventana_optimizacion": [str(v[0].date()) if v[0] is not None else None,
                                     str(v[1].date()) if v[1] is not None else None, v[2]],
            "monedas": self.monedas,
            "portafolios": list(self.pesos),
            "top_oportunidades": self.top,
            "mep_implicito": self.mep,
            "resumen_ic_backtest": self.resumen_ic,
            "avisos": self.avisos,
        }

    def guardar(self, carpeta=None) -> "Analisis":
        destino = carpeta or self.cfg.carpeta_registros or registro.carpeta_por_defecto()
        self.ruta_registro = registro.guardar_corrida(destino, self.metadata(), self.senales, self.pesos,
                                                      self.resumen, getattr(self, "asignacion_larga", None),
                                                      self.precios_hoy if hasattr(self, "precios_hoy")
                                                      else self.precios.loc[self.fecha_datos, self.activos])
        print(f"Corrida guardada en: {self.ruta_registro}")
        return self

    # ------------------------------------------------------------------------------------------- 7. salidas
    def figuras(self) -> list[tuple[str, object]]:
        nombres = dict(zip(self.senales.index, self.senales["nombre"]))
        figs = [
            ("Score de oportunidad", graficos.fig_ranking(self.senales, 30, nombres)),
            ("Por qué: percentiles de cada métrica", graficos.fig_mapa_senales(self.senales, 25)),
            ("Precio, medias y Bollinger de las oportunidades",
             graficos.fig_precios(self.precios, self.top or list(self.senales.index[:8]))),
        ]
        res = getattr(self, "portafolios", None)
        if res is not None and not res["cov"].empty:
            figs += [
                ("Frontera eficiente", graficos.fig_frontera(res["frontera"], res["mu"], res["cov"], self.pesos, self.rf)),
                ("Pesos por portafolio", graficos.fig_pesos(self.pesos)),
                ("Peso vs aporte al riesgo", graficos.fig_contribucion_riesgo(self.pesos, res["cov"])),
                ("Correlaciones", graficos.fig_correlaciones(res["cov"], portafolios.orden_hrp(res["cov"]))),
            ]
        if self.backtest is not None:
            figs += [("Backtest", graficos.fig_backtest(self.backtest["retornos"], self.benchmark)),
                     ("Capacidad predictiva del score", graficos.fig_ic(self.backtest["ic"]))]
        return figs

    def hojas_excel(self) -> dict[str, pd.DataFrame]:
        hojas = {
            "Senales": self.senales,
            "Metricas_riesgo": getattr(self, "metricas", None),
            "Fundamentales": self.fundamentales,
            "Calidad_datos": self.calidad,
            "Universo": self.universo,
        }
        if hasattr(self, "pesos"):
            hojas["Pesos"] = pd.DataFrame({NOMBRES.get(k, k): w for k, w in self.pesos.items()}).fillna(0.0)
            hojas["Resumen_portafolios"] = self.resumen
            hojas["Gemelos"] = self.tabla_gemelos
            hojas["Excluidos_optimizacion"] = self.excluidos_opt
        if hasattr(self, "asignacion_larga"):
            hojas["Que_comprar"] = self.asignacion_larga
        if self.tabla_cedears is not None:
            hojas["Precios_CEDEARs"] = self.tabla_cedears
        if self.backtest is not None:
            hojas["Backtest_metricas"] = self.backtest["metricas"]
            r = self.backtest["retornos"]
            mensual = (1 + r).groupby(r.index.to_period("M")).prod() - 1
            mensual.index = mensual.index.astype(str)
            hojas["Backtest_retornos_mes"] = mensual
            hojas["Backtest_IC"] = self.backtest["ic"]
            hojas["Backtest_pesos"] = self.backtest["pesos"]
        hojas["Notas"] = pd.DataFrame({"nota": [AVISO_LEGAL, f"Datos al {self.fecha_datos.date()}",
                                                f"Versión {__version__} · repo {registro.version_repo()}",
                                                f"Tasa libre de riesgo {self.rf:.2%} ({self.rf_fuente})"]
                                               + [f"Aviso: {a}" for a in self.avisos]})
        return hojas

    def exportar(self, nombre: str | None = None, descargar: bool = True) -> str:
        """Excel + reporte HTML + LEEME (+ la carpeta de la corrida si se guardó) en un ZIP."""
        d = exportar.carpeta_descargas()
        nombre = nombre or f"oportunidades_{self.fecha_datos:%Y%m%d}"
        xlsx = exportar.excel_resultados(self.hojas_excel(), d / f"{nombre}.xlsx")
        from . import tablas

        bloques = list(self.figuras())
        bloques.insert(1, ("Oportunidades detectadas", tablas.estilo_senales(
            self.senales, n=None, solo=["Oportunidad", "Oportunidad con alertas"])))
        if hasattr(self, "resumen"):
            bloques.insert(4, ("Resumen de portafolios", tablas.estilo_resumen_portafolios(
                self.resumen.drop(columns=["clave"]))))
        if self.backtest is not None:
            bloques.append(("Métricas del backtest", tablas.estilo_backtest(self.backtest["metricas"])))
        html = exportar.reporte_html(f"Oportunidades de inversión — datos al {self.fecha_datos.date()}", bloques,
                                     d / f"{nombre}.html", AVISO_LEGAL)
        leeme = d / "LEEME.txt"
        leeme.write_text(self._leeme(), encoding="utf-8")
        carpetas = [self.ruta_registro] if self.ruta_registro else []
        zp = exportar.zip_archivos([xlsx, html, leeme], d / f"{nombre}.zip", carpetas)
        print(f"ZIP: {zp}")
        if descargar:
            exportar.descargar_en_colab(zp)
        return str(zp)

    def _leeme(self) -> str:
        c = self.cfg
        return "\n".join([
            "OPORTUNIDADES DE INVERSIÓN — resultados de una corrida",
            f"Datos al: {self.fecha_datos.date()}   Versión: {__version__}   Repo: {registro.version_repo()}",
            f"Horizonte: {c.horizonte}   Ventana: {c.ventana_anios:g} años   Benchmark: {self.benchmark}",
            f"Capital: USD {c.capital_usd:,.0f}   Peso máximo: {c.peso_maximo:.0%}   Tasa libre de riesgo: {self.rf:.2%}",
            "",
            "Archivos:",
            "  *.xlsx  una hoja por tabla (señales, métricas, fundamentales, pesos, qué comprar, backtest...)",
            "  *.html  reporte con todos los gráficos interactivos (se abre con cualquier navegador, sin internet)",
            "  AAAAMMDD_HHMMSS/  la corrida tal como quedó registrada (si se guardó)",
            "",
            "Metodología: docs/METODOLOGIA.md del repo https://github.com/santiagoriverti/oportunidades_inversion",
            "",
            AVISO_LEGAL,
        ]) + "\n"

    # ------------------------------------------------------------------------------------------- todo junto
    def correr_todo(self, guardar: bool | None = None, exportar_zip: bool = False) -> "Analisis":
        self.cargar_datos().calcular_senales().optimizar().asignar()
        if self.cfg.correr_backtest:
            self.correr_backtest()
        if self.cfg.guardar_registro if guardar is None else guardar:
            self.guardar()
        if exportar_zip:
            self.exportar()
        return self
