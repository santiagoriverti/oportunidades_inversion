# Roadmap

Ideas y pendientes, en orden aproximado de valor. Nada de esto es necesario para usar la versión actual.

## Pendientes de verificación

- [ ] Correr los dos notebooks **en Colab** con la cuenta del usuario y comparar contra la corrida local (los
      notebooks se probaron en la PC con nbconvert; en Colab cambian la versión de Python, pandas y plotly).

## Próximas mejoras

1. **Módulo de renta fija argentina** (AO28, HJCLO, NPCDO, YMCXO y similares): un bono no se evalúa por su precio
   sino por su **TIR, duration y spread** contra la curva del emisor. Requiere el flujo de fondos de cada bono
   (cupones y amortizaciones; el usuario los tendría que cargar o hay que encontrar una fuente) y el precio en vivo
   de data912 (`/live/arg_bonds`, `/live/arg_corp`). "Artificialmente bajo" = TIR por encima de la curva para su
   duration y calidad.
2. **Valuación contra la propia historia** (P/E actual vs su promedio de 5-10 años): Yahoo gratis solo da 4 años
   de balances con huecos; necesitaría otra fuente (por ejemplo Financial Modeling Prep con API key).
3. **Robot semanal en GitHub Actions** que corra la lista por defecto y commitee el registro al repo (track record
   público). Se descartó en la versión 1 (el usuario eligió solo Drive); riesgo: Yahoo a veces bloquea las IPs de
   GitHub.
4. **Mínimo CVaR** (Rockafellar-Uryasev, programación lineal) como noveno portafolio (ver límite de 8 colores en
   `docs/ARQUITECTURA.md` §5).
5. **Restricciones por sector o por tipo** (por ejemplo, máximo 30% en tecnología, mínimo 10% en bonos).
6. **Rebalanceo de un portafolio existente**: dado lo que el usuario ya tiene, qué comprar/vender para llegar al
   objetivo minimizando operaciones.
7. **Alertas** (mail o Telegram) cuando un activo de la lista pasa a "Oportunidad".
8. **Ratios de CEDEAR** oficiales (BYMA) para mostrar cuántas acciones subyacentes representa cada CEDEAR.
9. **Simulación Monte Carlo** de la distribución de resultados de cada portafolio a 1 año.

## Hechos

- v0.1.0 (2026-11-06): versión inicial completa (ver `CHANGELOG.md`).
