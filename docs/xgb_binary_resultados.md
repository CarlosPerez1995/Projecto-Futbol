# Resultados de los modelos binarios over/under y BTTS (tarea 4.4)

**Resumen corto, actualizado el 11 nov tras cargar xG real a la BD y
volver a medir (decisión de Carlos): el xG no cambia la conclusión de
fondo — los 3 modelos siguen SIN poder predictivo real por encima de
una línea base trivial.** Se encontró además, al hacer esta
remedición, un bug real de calibración (ver sección dedicada) que se
corrigió en el código antes de reportar estos números.

## Bug encontrado y corregido: calibración isotónica inestable

Al re-medir con la feature de xG, el LogLoss de `btts` saltó de ~0.70
a 1.02 sin que el modelo hubiera cambiado de forma razonable. Antes de
reportar ese número como "el resultado real" se investigó la causa:
la calibración isotónica (`CalibratedClassifierCV(method="isotonic")`)
asigna probabilidad **exactamente 0.0** a la clase verdadera en varios
partidos de test (confirmado a mano: 2 de 526 en `over_1_5`, 5 de 526
en `btts`, 5 de 526 en el 1X2 — ver `docs/xgb_1x2_resultados.md`).
`log_loss` recorta esos ceros a un épsilon numérico, así que cada caso
así dispara una penalización enorme (~34 nats) que no refleja ninguna
mejora o empeoramiento real del modelo — es un artefacto. Causa
raíz: `val` tiene ~528 filas, insuficientes para que la regresión
isotónica (no paramétrica) generalice bien en los extremos; con ese
tamaño de muestra, la sigmoide (Platt, solo 2 parámetros) es mucho más
estable. Se verificó comparando las 3 variantes (sin calibrar /
isotónica / sigmoide) antes de decidir — las 3 coinciden entre sí
salvo la isotónica, que es la que se dispara.

**Corrección aplicada:** `calibrate_binary_model` y
`calibrate_xgb_1x2` ahora usan `method="sigmoid"` en vez de
`"isotonic"`. Esto afecta a los 3 modelos de esta tarea y al de 1X2
(4.3) — los números de ambos documentos están reportados ya con la
calibración corregida, no con la que tenía el bug.

## Efecto real del xG: comparación controlada (misma calibración en ambos lados)

Para no mezclar "mejoró por el fix de calibración" con "mejoró por el
xG", se entrenó cada modelo dos veces con la MISMA calibración
(sigmoide) y el MISMO split: una vez sin las 4 columnas nuevas de xG
(`xg_scored_avg_last5_home/away`, `xg_conceded_avg_last5_home/away`) y
una vez con ellas.

| Objetivo | AUC sin xG | AUC con xG | LogLoss sin xG | LogLoss con xG |
|---|---|---|---|---|
| `over_1_5` | 0.530 | 0.526 | 0.534 | 0.538 |
| `over_2_5` | 0.521 | **0.558** | 0.689 | 0.684 |
| `btts` | 0.537 | 0.507 | 0.684 | 0.686 |

El xG ayuda un poco en `over_2_5` (AUC +0.037) y no ayuda, o empeora
levemente, en los otros dos. Ninguno cruza el umbral del plan
(AUC > 0.6) ni antes ni después de agregar xG.

## Resultado final en TEST (con xG, calibración sigmoide corregida), comparado contra línea base trivial

| Objetivo | Tasa base (train) | AUC del modelo | LogLoss del modelo | LogLoss trivial | ¿Le gana a la trivial? |
|---|---|---|---|---|---|
| `over_1_5` | 0.771 | 0.526 | 0.538 | 0.537 | **No** (por un margen mínimo) |
| `over_2_5` | 0.530 | 0.558 | 0.684 | 0.689 | **Sí**, por un margen chico |
| `btts` | 0.542 | 0.507 | 0.686 | 0.685 | **No** |

**Criterio del plan (AUC > 0.6): sigue sin cumplirse en ninguno de los
3**, con o sin xG. `over_2_5` es el único que le gana a la trivial en
LogLoss, y por un margen (0.005) que no alcanza para decir que hay un
edge real.

## Por qué, probablemente (diagnóstico actualizado)

El diagnóstico de la corrida anterior (sin xG) seguía sin probar la
hipótesis central: que el xG, al ser una señal más directa del
desempeño ofensivo/defensivo de un partido, mejoraría estos mercados.
Ya probado — la mejora es marginal (`over_2_5`) o nula. Explicación más
probable, revisada: el xG que se cargó es un **promedio de los últimos
5 partidos del equipo** (mismo patrón `shift(1)` + `rolling` que las
demás features de forma, para no filtrar datos), no el xG del partido
puntual que se está prediciendo — que no existe antes de jugarse el
partido. Un promedio de 5 partidos, sea de goles o de xG, sigue
resumiendo "cómo le fue en general", no "cuántos goles habrá hoy", que
depende de factores partido a partido (lesiones, decisiones tácticas,
clima, suerte en el último tercio) que ninguna de las dos familias de
features captura. El problema de fondo no era la ausencia de xG — era
el nivel de granularidad (forma agregada vs. evento puntual).

## Corrección a los resultados de 4.2 y 4.3 reportados antes del 11 nov

Los números reportados en la corrida anterior a esta (antes de cargar
xG) usaban calibración isotónica, que resultó inestable (ver arriba).
Esos números concretos (`over_1_5`: AUC 0.547/LogLoss 0.866; `over_2_5`:
AUC 0.511/LogLoss 0.827; `btts`: AUC 0.536/LogLoss 0.752) quedan
obsoletos — no se puede saber, sin volver a correrlos con sigmoide, qué
parte de esos LogLoss altos era el bug de calibración y qué parte era
el modelo real. La tabla de esta sección (arriba, "comparación
controlada") es la que hay que usar para comparar antes/después de xG.

El Poisson/Dixon-Coles (4.2) no usa `predictor_columns()` — se ajusta
directamente por máxima verosimilitud sobre los goles de cada
liga/temporada, sin ninguna feature de equipo. **No consume el xG
nuevo y sus resultados no cambian** (ver `docs/dixon_coles_resultados.md`,
sin modificar). Si se quisiera que Dixon-Coles también aprovechara el
xG, habría que extender el modelo explícitamente (no es automático) —
no se hizo, no estaba en el pedido de esta tarea.

## Conclusión honesta para Carlos

El resultado real, con xG cargado y la calibración corregida: **el xG
no cambia la conclusión de fase 4** — ninguno de los 3 mercados
binarios ni el 1X2 muestra una ventaja clara y consistente sobre
conocer las tasas históricas. `over_2_5` mejora un poco con xG pero
sigue sin cruzar el criterio del plan. El pipeline completo (BD →
features → split sin fuga → entrenamiento/calibración/evaluación)
sigue funcionando correctamente — lo que falta no es un bug, es una
señal predictiva más fuerte que un promedio de 5 partidos (de goles o
de xG) por equipo. Fase 5 (capa prescriptiva) sigue en pausa hasta que
Carlos decida cómo seguir.
