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
5. **Backtesting histórico** — **en pausa**, pendiente de que Carlos
   decida si se corre ya para `1X2`/`over_1_5`/`over_2_5` (que sí
   tienen edge demostrado) excluyendo `btts`, o se espera más (ver
   punto de decisión abajo).
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

**Punto de decisión actualizado (11 nov, tras la ronda de cuotas) —
la situación cambió de forma real**: `1X2`, `over_1_5` y `over_2_5`
ya tienen una ventaja demostrada sobre la línea base trivial;
`over_1_5`/`over_2_5` cumplen el criterio del plan (AUC>0.6). `btts`
sigue sin funcionar, y el Dixon-Coles sigue sin verse afectado por
ninguna de las dos rondas (no consume estas features). Opciones para
Carlos: (1) avanzar a Fase 5 con los 3 modelos que sí funcionan,
excluyendo `btts` explícitamente, (2) buscar una cuota de mercado
específica de BTTS antes de decidir sobre ese mercado puntual, o (3)
pausar Fase 4/5 del todo por otro motivo. **Fase 5 sigue en pausa
hasta esta decisión.**

## Fase 5 — Capa prescriptiva

**En pausa** (ver punto de decisión arriba). Depende de Fase 4
completa Y de tener al menos un modelo con ventaja demostrada sobre la
línea base trivial, no solo "con probabilidades calibradas".

1. **Valor esperado y Kelly fraccionado** — las fórmulas que deciden
   si una apuesta vale la pena (`EV`) y cuánto arriesgar si sí (`Kelly`,
   acotado a un porcentaje máximo del banco).
2. **Recomendaciones diarias** — un archivo generado automáticamente
   con los partidos de los próximos días que valga la pena apostar,
   según el modelo.
3. **Registro de apuestas y resultados** — para medir, con el tiempo,
   si las recomendaciones realmente dan plata o no.

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
