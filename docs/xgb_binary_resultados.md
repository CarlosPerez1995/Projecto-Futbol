# Resultados de los modelos binarios over/under y BTTS (tarea 4.4)

**Resumen corto: el código funciona correctamente (pipeline
verificado con tests y a mano), pero los 3 modelos NO tienen poder
predictivo real por encima de una línea base trivial.** Esto no es un
detalle menor para archivar — motivó revisar también los resultados ya
reportados de 4.2 y 4.3, ver la sección final de este documento.

## Resultado en TEST, comparado contra una línea base trivial

La línea base trivial es: predecir siempre la tasa base del objetivo
medida en `train` (ej. "este mercado se cumplió en el 53% de los
partidos de entrenamiento, predecir 0.53 para todos los partidos de
test").

| Objetivo | Tasa base (train) | AUC del modelo | LogLoss del modelo | LogLoss trivial | ¿El modelo le gana a la trivial? |
|---|---|---|---|---|---|
| `over_1_5` | 0.771 | 0.547 | 0.866 | **0.537** | **No** |
| `over_2_5` | 0.530 | 0.511 | 0.827 | **0.690** | **No** |
| `btts` | 0.542 | 0.536 | 0.752 | **0.685** | **No** |

**Criterio del plan (AUC > 0.6): no se cumple en ninguno de los 3.**
Un AUC de 0.51-0.55 es, en la práctica, indistinguible de adivinar al
azar (0.5) — el modelo no está encontrando una relación real entre las
features de forma de equipo y estos 3 mercados.

## Por qué, probablemente (diagnóstico, no una excusa)

Se descartó que fuera un bug de la calibración antes de escribir esta
conclusión: se comparó el modelo sin calibrar, calibrado con isotónica
y calibrado con sigmoide (Platt) para el modelo de 1X2 (tarea 4.3) —
los tres dan un LogLoss casi idéntico en test (1.081 / 1.090 / 1.076),
así que la calibración no es la causa de que el modelo no supere la
línea base. El LogLoss en `train` (0.962, antes de calibrar) sí es
mejor que en `val`/`test` (~1.05-1.09) — el modelo encuentra *algo* en
los datos de entrenamiento, pero ese algo no generaliza.

La explicación más probable: **las features de forma de equipo de la
Fase 3 (promedios de goles/puntos/rachas de los últimos 5 partidos)
capturan razonablemente bien "quién es mejor que quién" para el
resultado 1X2, pero no alcanzan para predecir el total de goles de un
partido puntual** — eso depende mucho de factores partido a partido
(lesiones, decisiones tácticas, suerte en el último tercio) que un
promedio de 5 partidos no resume. El xG (gol esperado, de Understat)
sería una señal mucho más directa para estos mercados específicamente
— y es exactamente el pendiente que ya estaba documentado desde la
Fase 3 (`INFORME_PENDIENTES.md`: "cargar xG a la base de datos"), sin
cargar todavía. Esto no es una coincidencia menor: refuerza que ese
pendiente, hasta ahora "cuando convenga", debería priorizarse antes de
seguir construyendo sobre estos 3 mercados.

## Corrección honesta a los resultados ya reportados de 4.2 y 4.3

Al encontrar este problema se revisó también contra una línea base
trivial el modelo Poisson/Dixon-Coles (4.2) y el de clasificación 1X2
(4.3), que no se habían comparado contra ninguna línea base al
reportarlos — un error de omisión, corregido acá:

- **1X2 (XGBoost, 4.3):** LogLoss del modelo en test = 1.090; LogLoss
  trivial (predecir siempre la proporción H/D/A de train) = **1.078**.
  **El modelo queda ligeramente PEOR que la trivial.** Cumplía el
  número exacto que pedía el plan ("<1.1"), pero ese número por sí
  solo no demuestra que el modelo aporte nada por encima de simplemente
  conocer las proporciones históricas de local/empate/visitante.
- **Poisson/Dixon-Coles (4.2):** comparado liga por liga contra RPS
  trivial (base rate de train) en test: gana claro en GER-Bundesliga
  (0.212 vs 0.239 trivial) e ITA-Serie A (0.226 vs 0.239), empata
  aproximadamente en ESP-La Liga (0.218 vs 0.220), y queda ligeramente
  peor en ENG-Premier League (0.231 vs 0.223) y FRA-Ligue 1 (0.238 vs
  0.236). Mixto: el modelo estadístico sí aporta algo en 2 de 5 ligas,
  es prácticamente indistinguible de la trivial en las otras 3 — no es
  el resultado contundente que parecía al solo mirar "¿está por debajo
  de 0.25?" sin comparar contra nada.

**Conclusión honesta para Carlos, antes de seguir a Fase 5:** el
pipeline completo (extracción → BD → features → split sin fuga →
3 modelos entrenados/calibrados/evaluados correctamente, con su propio
código probado) funciona de punta a punta. Lo que todavía no está
claro es si, con las features actuales, alguno de estos modelos aporta
una ventaja real y consistente por encima de simplemente conocer las
tasas históricas. Antes de construir la capa prescriptiva (Fase 5 —
decidir cuánto apostar con dinero real) sobre un modelo sin edge
demostrado, tiene sentido: (1) cargar xG a la BD (pendiente ya
conocido) y volver a medir, y/o (2) decidir con Carlos si avanzar
Fase 5 de todos modos con las salvedades claras, o pausar fase 4 ahí.
