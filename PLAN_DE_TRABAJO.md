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
   el 11 nov con xG**: `src/futbol/models/xgb_1x2.py`. LogLoss 1.073 en
   test (calibración sigmoide, corregida — ver más abajo), vs. 1.078 de
   la línea base trivial: mejora de 0.005, no significativa. Ver
   `docs/xgb_1x2_resultados.md`. Cada versión del modelo se guarda con
   sus métricas y el hash del dataset con que se entrenó
   (`models/xgb_1x2/<version>/model.pkl` + `metrics.json`).
4. ~~**Modelos de over/under y BTTS**~~ — **Hecho, re-medido el 11 nov
   con xG**: `src/futbol/models/xgb_binary.py`. **Ningún AUC pasa de
   0.56** (el plan pedía >0.6) — solo `over_2_5` le gana a la línea
   base trivial en LogLoss, por un margen chico. Ver
   `docs/xgb_binary_resultados.md`.
5. **Backtesting histórico** — **en pausa**, no tiene sentido simular
   rentabilidad de apuestas con modelos sin edge demostrado todavía
   contra una línea base trivial (ver punto de decisión abajo).
6. ~~**Cargar xG real y volver a medir**~~ — **Hecho (11 nov, decisión
   de Carlos ejecutada)**: `home_xg`/`away_xg` reales cargados en
   `matches` (`db/schema_v4.sql`, `load_xg`), features de xG rodante
   por equipo agregadas (`xg_scored_avg_last5`/`xg_conceded_avg_last5`,
   mismo patrón sin fuga que las de goles). **Resultado real: el xG no
   cambia la conclusión** — mejora marginal en 1X2 y en `over_2_5`, sin
   cambio o levemente peor en los otros dos mercados, ninguno cruza el
   umbral del plan. Al remedir se encontró además un bug de calibración
   isotónica (corregido, pasó a sigmoide) — detalle completo en
   `docs/xgb_binary_resultados.md`.

**Punto de decisión actualizado (11 nov) — el candidato más directo
para mejorar ya se probó y no alcanzó**: con xG cargado, los 3 modelos
XGBoost y el Dixon-Coles (no afectado por el xG, no lo consume) siguen
sin mostrar una ventaja clara y consistente sobre simplemente conocer
las tasas históricas. Opciones para Carlos: (1) seguir a Fase 5 de
todos modos sabiendo las salvedades, (2) buscar otra señal predictiva
más fuerte (ej. cuotas de mercado como feature, ya están en la BD
desde Fase 2 pero no se usan como predictoras; alineaciones/lesiones),
o (3) pausar Fase 4/5 del todo. **Fase 5 sigue en pausa hasta esta
decisión** — construir una capa de apuestas reales sobre un modelo sin
edge demostrado sería irresponsable.

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
