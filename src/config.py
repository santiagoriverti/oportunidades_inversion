"""Parámetros del análisis.

Los notebooks arman la configuración con ``Config.desde_horizonte("mediano", ...)``: el horizonte fija
valores por defecto coherentes (ventana histórica, rebalanceo del backtest, pesos del score, plazos del
seguimiento) y cualquier parámetro se puede pisar por nombre.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RUTA_UNIVERSO = RAIZ / "data" / "universo.csv"

# Perfiles por horizonte de inversión (decisión del usuario 2026-11-06: "mediano" por defecto).
HORIZONTES: dict[str, dict] = {
    "corto": {  # 1-3 meses
        "anios_historia": 6.0,
        "ventana_anios": 1.5,
        "rebalanceo": "M",
        "plazos_expost": [21, 63],
        "pesos_grupos": {"tecnico": 0.50, "estadistico": 0.35, "fundamental": 0.15},
    },
    "mediano": {  # 6-12 meses
        "anios_historia": 8.0,
        "ventana_anios": 3.0,
        "rebalanceo": "Q",
        "plazos_expost": [21, 63, 126, 252],
        "pesos_grupos": {"tecnico": 0.40, "estadistico": 0.30, "fundamental": 0.30},
    },
    "largo": {  # 3+ años
        "anios_historia": 12.0,
        "ventana_anios": 5.0,
        "rebalanceo": "S",
        "plazos_expost": [63, 126, 252, 504],
        "pesos_grupos": {"tecnico": 0.25, "estadistico": 0.25, "fundamental": 0.50},
    },
}

# Umbrales de las "señales absolutas" (cada una que se cumple suma 1 a n_senales). Ver docs/METODOLOGIA.md §3.
UMBRALES_SENALES: dict[str, float] = {
    "dist_sma200": 0.0,          # precio debajo de la media de 200 días
    "zscore_1a": -1.5,           # log-precio 1,5 desvíos debajo de su media de 1 año
    "z_tendencia_3a": -1.5,      # 1,5 desvíos debajo de su tendencia de 3 años
    "rsi_14": 30.0,              # RSI sobrevendido
    "bollinger_pctb": 0.0,       # debajo de la banda inferior de Bollinger
    "drawdown_52s": -0.25,       # caída de 25% o más desde el máximo de 52 semanas
    "z_ret_3m": -1.5,            # caída de 3 meses inusual para el propio activo
    "z_relativo_bench": -1.5,    # muy por debajo de lo normal contra el benchmark
    "upside_analistas": 0.20,    # precio objetivo promedio 20% o más arriba (3+ analistas)
    "pe_relativo_sector": 0.80,  # P/E 20% o más debajo del ETF de su sector
    "peg": 1.0,                  # PEG positivo y menor a 1
}


@dataclass
class Config:
    """Todos los parámetros del análisis (ver docs/METODOLOGIA.md para el detalle de cada uno)."""

    # --- Universo ---
    tickers: list[str] | None = None        # None = data/universo.csv (lista original del usuario)
    horizonte: str = "mediano"
    benchmark: str = "SPY"

    # --- Datos ---
    anios_historia: float = 8.0              # años que se descargan (señales largas + backtest)

    # --- Modelo de riesgo y retorno ---
    ventana_anios: float = 3.0               # ventana para covarianza, retornos esperados y métricas
    frecuencia_riesgo: str = "W"             # "W" semanal (recomendado: BTC y ETFs europeos no cotizan en
                                             # el mismo horario que EE.UU.) o "D" diaria
    cobertura_minima: float = 0.90           # fracción de la ventana con precios para entrar a optimizar
    metodo_retornos: str = "historico"       # "historico" (CAGR de la ventana) o "capm"
    tasa_libre_riesgo: float | None = None   # None = T-bill 13 semanas (^IRX) de Yahoo

    # --- Gemelos (activos casi idénticos: GLD/IAU, SPY/VOO...) ---
    deduplicar: bool = True
    umbral_gemelos: float = 0.99             # correlación semanal mínima
    ratio_vol_gemelos: float = 1.25          # y volatilidades parecidas (SSO, apalancado 2x, no es gemelo de SPY)

    # --- Restricciones de los portafolios ---
    peso_maximo: float = 0.20
    peso_minimo: float = 0.02                # posiciones más chicas se eliminan y se renormaliza
    volatilidad_objetivo: float = 0.10       # portafolio "volatilidad objetivo" (perfil moderado)
    top_n_oportunidades: int = 10

    # --- Score de oportunidad ---
    pesos_grupos: dict = field(default_factory=lambda: dict(HORIZONTES["mediano"]["pesos_grupos"]))
    umbrales_senales: dict = field(default_factory=lambda: dict(UMBRALES_SENALES))
    umbral_score_oportunidad: float = 70.0
    min_senales_oportunidad: int = 2
    incluir_fundamentales: bool = True

    # --- Black-Litterman (vistas = score de oportunidad) ---
    bl_tau: float = 0.05
    bl_intensidad: float = 0.25              # Sharpe extra de la vista para un score de 100 (y negativo para 0)

    # --- Qué comprar ---
    capital_usd: float = 10_000.0
    permitir_fracciones: bool = False
    incluir_cedears: bool = True

    # --- Backtest ---
    correr_backtest: bool = True
    rebalanceo: str = "Q"                    # "M" mensual, "Q" trimestral, "S" semestral
    costo_bps: float = 10.0                  # costo por rotación (puntos básicos sobre lo operado)

    # --- Seguimiento y registro ---
    plazos_expost: list[int] = field(default_factory=lambda: [21, 63, 126, 252])  # días hábiles
    guardar_registro: bool = True
    carpeta_registros: str | None = None     # None = Google Drive en Colab, ./registros_local en la PC
    ruta_universo: str = str(RUTA_UNIVERSO)

    @classmethod
    def desde_horizonte(cls, horizonte: str = "mediano", **kwargs) -> "Config":
        """Config con los valores por defecto del horizonte ("corto", "mediano", "largo")."""
        if horizonte not in HORIZONTES:
            raise ValueError(f"horizonte debe ser uno de {list(HORIZONTES)}; llegó {horizonte!r}")
        base = copy.deepcopy(HORIZONTES[horizonte])
        base.update(kwargs)
        cfg = cls(horizonte=horizonte, **base)
        cfg.validar()
        return cfg

    def validar(self) -> None:
        """Frena con un mensaje claro si algún parámetro no tiene sentido."""
        errores = []
        if self.horizonte not in HORIZONTES:
            errores.append(f"horizonte debe ser uno de {list(HORIZONTES)}")
        if self.frecuencia_riesgo not in ("D", "W"):
            errores.append('frecuencia_riesgo debe ser "D" o "W"')
        if self.metodo_retornos not in ("historico", "capm"):
            errores.append('metodo_retornos debe ser "historico" o "capm"')
        if self.rebalanceo not in ("M", "Q", "S"):
            errores.append('rebalanceo debe ser "M", "Q" o "S"')
        if not 0 < self.peso_maximo <= 1:
            errores.append("peso_maximo debe estar entre 0 y 1")
        if not 0 <= self.peso_minimo < self.peso_maximo:
            errores.append("peso_minimo debe ser >= 0 y menor que peso_maximo")
        if not 0 < self.cobertura_minima <= 1:
            errores.append("cobertura_minima debe estar entre 0 y 1")
        if self.ventana_anios <= 0 or self.anios_historia < self.ventana_anios:
            errores.append("ventana_anios debe ser > 0 y anios_historia >= ventana_anios")
        if self.capital_usd <= 0:
            errores.append("capital_usd debe ser positivo")
        if self.volatilidad_objetivo <= 0:
            errores.append("volatilidad_objetivo debe ser positiva")
        if self.top_n_oportunidades < 2:
            errores.append("top_n_oportunidades debe ser al menos 2")
        if not 0 < self.umbral_gemelos <= 1:
            errores.append("umbral_gemelos debe estar entre 0 y 1")
        faltan = {"tecnico", "estadistico", "fundamental"} - set(self.pesos_grupos)
        if faltan:
            errores.append(f"pesos_grupos necesita las claves {sorted(faltan)}")
        elif sum(max(float(v), 0.0) for v in self.pesos_grupos.values()) <= 0:
            errores.append("pesos_grupos debe tener algún peso positivo")
        if self.tickers is not None and len([t for t in self.tickers if str(t).strip()]) == 0:
            errores.append("tickers está vacío: usá None para el universo por defecto")
        if errores:
            raise ValueError("Configuración inválida:\n - " + "\n - ".join(errores))

    def como_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def desde_dict(cls, d: dict) -> "Config":
        """Reconstruye un Config guardado (ignora claves desconocidas de versiones viejas)."""
        nombres = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in nombres})
