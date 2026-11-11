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
3. ~~**Modelo de clasificación 1X2** (XGBoost)~~ — **Hecho (11 nov)**:
   `src/futbol/models/xgb_1x2.py`. LogLoss 1.090 en test, cumple el
   número exacto del plan (<1.1) — **corrección agregada el 11 nov**:
   la línea base trivial da 1.078, el modelo queda ligeramente PEOR.
   Ver `docs/xgb_1x2_resultados.md`. Cada versión del modelo se guarda
   con sus métricas y el hash del dataset con que se entrenó
   (`models/xgb_1x2/<version>/model.pkl` + `metrics.json`).
4. ~~**Modelos de over/under y BTTS**~~ — **Hecho (11 nov)**, con un
   hallazgo real importante: `src/futbol/models/xgb_binary.py`, mismo
   patrón que 1X2. **Ningún AUC pasa de 0.55** (el plan pedía >0.6) —
   los 3 modelos quedan peor que la línea base trivial en test.
   Descartado que sea un bug de calibración (comparado isotónica vs.
   sigmoide vs. sin calibrar: resultado casi idéntico en los tres
   casos). Diagnóstico completo, y la corrección retroactiva de 4.2/4.3
   de arriba, en `docs/xgb_binary_resultados.md`.
5. **Backtesting histórico** — **en pausa**, no tiene sentido simular
   rentabilidad de apuestas con modelos sin edge demostrado todavía
   contra una línea base trivial (ver punto de decisión abajo).

**Punto de decisión antes de seguir — ya no es "cuando convenga"
como decía esta misma sección antes del 11 nov**: los 3 modelos
entrenados hasta ahora (Dixon-Coles, XGBoost 1X2, XGBoost over/under y
BTTS) no muestran una ventaja clara y consistente sobre simplemente
conocer las tasas históricas. El candidato más directo para mejorar
esto es cargar el xG de Understat a la base de datos (pendiente desde
Fase 2/3, ver `INFORME_PENDIENTES.md`) — especialmente relevante para
over/under y BTTS, donde el xG debería ser una señal mucho más directa
que promedios de goles de los últimos 5 partidos. Recomendación: cargar
xG y volver a medir antes de avanzar a Fase 5, o que Carlos decida
seguir de todos modos sabiendo las salvedades. **Fase 5 queda en pausa
hasta esta decisión** — construir una capa de apuestas reales sobre un
modelo sin edge demostrado sería irresponsable.

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
Cargar xG de Understat YA NO es "cuando convenga" — ver el punto de
decisión de Fase 4 arriba, pasó a ser el paso recomendado antes de
seguir.)
