# Plan de trabajo — Fútbol

*Última actualización: 11 nov 2026. Qué sigue y en qué orden, a partir
de donde está hoy el proyecto (fases 0-3 completas, fase 4 arrancada,
ver `INFORME_PROYECTO.md`). Basado en el plan arquitectónico original
(`~/Escritorio/AuditoriaFutbol/Planes arquitectonicos/`, fuera de este
repo) ajustado con lo que realmente se construyó.*

## Fase 4 — Modelos predictivos

Depende de Fase 3 (hecha). F9 (instalar `scikit-learn`/`scipy`/
`xgboost`/`joblib`) ya autorizada y hecha el 11 nov. Orden sugerido,
cada uno construido sobre el anterior:

1. ~~**Split temporal para backtesting**~~ — **Hecho (11 nov)**:
   `src/futbol/models/split.py`, 70/15/15 por fecha, nunca mezclado al
   azar, con ajuste de corte para garantizar cero overlap de fechas
   entre splits incluso con partidos repetidos en la misma fecha/hora.
   Validado contra el dataset real: 2.461/528/526 filas, proporciones
   exactas, sin overlap.
2. ~~**Modelo Poisson/Dixon-Coles**~~ — **Hecho (11 nov)**:
   `src/futbol/models/poisson_dixon_coles.py`, un modelo por liga y
   temporada. RPS < 0.25 en test en las 5 ligas (número exacto del
   plan cumplido) — pero **corrección agregada el 11 nov** al comparar
   contra una línea base trivial (predecir siempre la proporción
   histórica de train): el modelo le gana claro en 2 de 5 ligas, es
   indistinguible en 1, y queda ligeramente peor en 2. Detalle y el
   ejemplo real (ratings que coinciden con los 3 descendidos reales de
   la Premier League 2024-25) en `docs/dixon_coles_resultados.md`.
3. ~~**Modelo de clasificación 1X2** (XGBoost)~~ — **Hecho, re-medido
   el 11 nov en dos rondas (xG, luego cuotas de mercado)**:
   `src/futbol/models/xgb_1x2.py`. **Resultado final: LogLoss 1.037 en
   test (calibración sigmoide, corregida — ver más abajo), le gana a la
   trivial (1.078) con margen real** (0.041 — la ronda de solo xG daba
   0.003, no significativa). Ver `docs/xgb_1x2_resultados.md`. Cada
   versión del modelo se guarda con sus métricas y el hash del dataset
   con que se entrenó (`models/xgb_1x2/<version>/model.pkl` +
   `metrics.json`).
4. ~~**Modelos de over/under y BTTS**~~ — **Hecho, re-medido el 11 nov
   en dos rondas**: `src/futbol/models/xgb_binary.py`. **Resultado
   final: `over_1_5` (AUC 0.601) y `over_2_5` (AUC 0.604) cruzan por
   primera vez el criterio del plan (>0.6)** y le ganan a la trivial
   con margen real. `btts` sigue sin funcionar — empeora con las
   cuotas (AUC 0.453, peor que azar), no tiene cuota de mercado
   dedicada en este dataset. Ver `docs/xgb_binary_resultados.md`.
5. ~~**Backtesting histórico**~~ — **Hecho (11 nov, tercera ronda,
   tras la decisión de Carlos de avanzar a Fase 5 con 1X2/over_1_5/
   over_2_5)**: `src/futbol/betting/backtest.py`, simula apostar con
   EV positivo + Kelly fraccionado usando cuotas REALES de cierre
   sobre el split `test` nunca visto en entrenamiento/calibración.
   **Resultado real, crítico: la estrategia pierde dinero de forma
   severa** — 1X2 pierde 85% del banco simulado, over/under 2.5 pierde
   49%; `over_1_5` no se pudo backtestear (no hay cuota de mercado de
   ese total cargada en este dataset). Verificado a fondo que no es un
   bug: cuando el modelo se aparta de la cuota de mercado, el mercado
   resulta ser más acertado que el modelo, no al revés — el "edge"
   medido contra la línea base trivial no es el mismo tipo de edge que
   hace falta para apostar rentablemente contra ese mercado. Detalle
   completo en `docs/backtest_resultados.md`.
6. ~~**Cargar xG real y volver a medir**~~ — **Hecho (11 nov, primera
   ronda, decisión de Carlos ejecutada)**: `home_xg`/`away_xg` reales
   cargados en `matches` (`db/schema_v4.sql`, `load_xg`), features de
   xG rodante por equipo agregadas (`xg_scored_avg_last5`/
   `xg_conceded_avg_last5`, mismo patrón sin fuga que las de goles).
   **Resultado real: el xG por sí solo no alcanzaba** — mejora marginal
   en 1X2 y en `over_2_5`, sin cambio o levemente peor en los otros dos
   mercados. Al remedir se encontró además un bug de calibración
   isotónica (corregido, pasó a sigmoide) — detalle completo en
   `docs/xgb_binary_resultados.md`.
7. ~~**Cuotas de mercado como feature**~~ — **Hecho (11 nov, segunda
   ronda, decisión de Carlos ejecutada)**: `src/futbol/features/odds.py`,
   probabilidad implícita de la cuota de cierre promedio (mercados 1x2
   y over/under 2.5, ya cargados en Fase 2). **Resultado real: esta sí
   funciona** — ver puntos 3 y 4 arriba. Las 4 columnas de cuotas pasan
   a ser, por lejos, las features más importantes del modelo 1X2 (~48%
   de la importancia total).

**Punto de decisión del 11 nov, tras la ronda de cuotas (superado por
el hallazgo del backtesting, ver abajo)**: Carlos decidió avanzar a
Fase 5 con `1X2`/`over_1_5`/`over_2_5`, excluyendo `btts`. Al construir
el primer paso real de Fase 5 (backtesting + EV/Kelly) se encontró que
esa ventaja (medida en LogLoss/AUC contra la trivial) **no se traduce
en apostar rentablemente** contra el mercado — ver
`docs/backtest_resultados.md`. El Dixon-Coles sigue sin verse afectado
por ninguna ronda de Fase 4 (no consume estas features).

## Fase 5 — Capa prescriptiva

**Bloqueada por un hallazgo real, no por falta de decisión**: al
construir el punto 1 (EV + Kelly) y backtestearlo contra cuotas reales
(`src/futbol/betting/`), la estrategia "apostar con EV positivo" pierde
85% del banco simulado en 1X2 y 49% en over/under 2.5 — ver
`docs/backtest_resultados.md` para el detalle completo, incluida la
verificación de que no es un bug de código. **No se construyeron los
puntos 2 y 3 sobre esta base ya demostrada perdedora** — hacerlo sería
automatizar, a mayor escala, una estrategia que el propio backtesting
de este mismo punto 1 descartó. Queda pendiente de que Carlos decida
cómo seguir (ver `INFORME_PENDIENTES.md`).

1. ~~**Valor esperado y Kelly fraccionado**~~ — **Hecho (11 nov)**:
   `src/futbol/betting/ev_kelly.py` (fórmulas, con la advertencia
   matemática de por qué un modelo que usa la cuota de mercado como
   feature no necesariamente da ventaja real para apostar) +
   `src/futbol/betting/backtest.py` (backtest real, resultado arriba).
2. **Recomendaciones diarias** — **no construido**, pendiente de que
   se resuelva el bloqueante de arriba. Construirlo ahora generaría
   recomendaciones de apuestas reales sobre una estrategia que ya se
   demostró perdedora en backtesting.
3. **Registro de apuestas y resultados** — **no construido**, mismo
   motivo que el punto 2.

## Fase 6 — Operación

Depende de Fase 5.

1. **Pipeline orquestado** — un script que corra todo el flujo de
   punta a punta (extracción → carga → features → modelos →
   recomendaciones) en un solo comando, registrando cada etapa en la
   tabla `pipeline_runs` que ya existe en el esquema desde la Fase 2.
2. **Automatización diaria** — `systemd timer` (ya se usa este patrón
   en otro frente del hub, Punky Soluciones, con buenos resultados),
   para que corra solo sin depender de que alguien lo arranque a mano.
3. **Cobertura de tests ≥40%** — cierre de cobertura, no arranque
   desde cero: cada fase ya viene con sus propios tests (91 hoy), así
   que el trabajo real acá es medir qué falta, no escribir todo de
   nuevo.
4. **Documentación final** — `README.md` con diagrama de flujo
   (reutilizable del que ya está en `INFORME_ARQUITECTURA.md`).

## Trabajo que se puede intercalar en cualquier momento, sin bloquear nada

- Limpiar la carpeta `~/Escritorio/proyectos` redundante.

(Los mercados de cuotas over/under y hándicap asiático que estaban en
esta lista ya se implementaron el 10 nov — ver `INFORME_PENDIENTES.md`.
Cargar xG de Understat y volver a medir, que estaba acá como paso
recomendado, se hizo el 11 nov — ver el punto de decisión de Fase 4
arriba para el resultado real.)
