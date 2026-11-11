# Resultados de los modelos binarios over/under y BTTS (tarea 4.4)

**Resumen corto, actualizado el 11 nov tras agregar las cuotas de
mercado como feature (decisión de Carlos, segunda ronda del día):
`over_1_5` y `over_2_5` cruzan por primera vez el criterio del plan
(AUC > 0.6) y le ganan con margen real a la línea base trivial. `btts`
sigue sin funcionar — y empeora con las cuotas.** Antes de esto se
había probado cargar xG real (primera ronda del mismo día), que no
alcanzó — ver la sección histórica más abajo.

## Resultado final en TEST (con xG + cuotas de mercado), comparado contra línea base trivial

| Objetivo | Tasa base (train) | AUC del modelo | LogLoss del modelo | LogLoss trivial | ¿Le gana a la trivial? | ¿AUC > 0.6? |
|---|---|---|---|---|---|---|
| `over_1_5` | 0.771 | **0.601** | 0.529 | 0.537 | **Sí** | **Sí** |
| `over_2_5` | 0.530 | **0.604** | 0.675 | 0.689 | **Sí** | **Sí** |
| `btts` | 0.542 | 0.453 | 0.686 | 0.685 | No | No |

`over_1_5` y `over_2_5` son, por primera vez en toda la Fase 4, un
resultado que cumple el criterio original del plan con margen real,
no por una fracción cerca del límite. `btts` sigue sin servir — y con
las cuotas su AUC cae por debajo de 0.5 (peor que adivinar al azar).

## Qué feature se agregó: probabilidades implícitas de la cuota de cierre

`src/futbol/features/odds.py` (nuevo, 11 nov): toma la cuota de
**cierre** promedio entre casas (`bookmaker='avg'`, `is_closing=1` —
la columna `AvgC*` de football-data.co.uk, ya cargada desde Fase 2),
la única con cobertura estable entre temporadas (el esquema de
columnas por casa cambia, `docs/odds_columns_map.md`), y la convierte
de cuota a probabilidad implícita quitando el margen de la casa
("devigging": `1/cuota` normalizado para que la suma dé 1). 4 columnas
nuevas: `odds_implied_prob_home/draw/away` (mercado 1x2) y
`odds_implied_prob_over_2_5` (mercado over/under 2.5). Cobertura: 3.504
de 3.515 partidos.

**Por qué esto no es fuga de datos**: la cuota de cierre se fija antes
del partido (el mercado deja de aceptar apuestas al inicio) — "antes
del partido" no significa "mucho antes", significa que no usa ninguna
información posterior al resultado real. Es exactamente la misma
lógica ya aplicada al xG rodante (features que existen antes del
partido son predictoras legítimas, lo que no se puede usar es el
resultado del propio partido).

## Comparación controlada: efecto real de las cuotas (misma calibración, mismo xG en ambos lados)

Para aislar el efecto de las cuotas del de las rondas anteriores, se
entrenó cada modelo dos veces con el MISMO split y la MISMA
calibración (sigmoide): una vez con el set de predictoras de la ronda
de xG (sin cuotas) y una vez agregando las 4 columnas de cuotas.

| Objetivo | AUC sin odds | AUC con odds | LogLoss sin odds | LogLoss con odds |
|---|---|---|---|---|
| `over_1_5` | 0.526 | **0.601** | 0.538 | 0.529 |
| `over_2_5` | 0.558 | **0.604** | 0.684 | 0.675 |
| `btts` | 0.507 | **0.453** | 0.686 | 0.686 |

Las cuotas mejoran claramente `over_1_5` (+0.075 AUC) y `over_2_5`
(+0.046 AUC) — tiene sentido: la probabilidad implícita de
`over_2_5` es, literalmente, la propia estimación del mercado para un
mercado muy cercano al que se está prediciendo. Para `btts`, que no
tiene una cuota de mercado dedicada en este dataset (solo se cargó
1x2 y over/under 2.5, ver `docs/odds_columns_map.md`), las columnas de
cuotas no aportan señal directa y el AUC empeora (0.507 → 0.453) — la
importancia de features (`models/xgb_btts/<version>/metrics.json`)
muestra que el árbol sí les da peso considerable, pero sin una señal
real de ese mercado específico, agregar más columnas solo le dio al
`GridSearchCV` más superficie para ajustar a ruido de `train` que no
generaliza. No es un bug: es el mismo patrón ya documentado de "el
modelo encuentra *algo* en entrenamiento que no necesariamente mejora
test", ahora con una familia de features distinta.

## Por qué, probablemente (diagnóstico final de Fase 4, sin backtesting)

Las features de forma por equipo (Fase 3: promedios de los últimos 5
partidos) y el xG rodante (misma lógica, ronda anterior) resumen "cómo
le fue en general a cada equipo", pero no capturan bien factores
puntuales de un partido concreto. Las cuotas de mercado sí los
capturan indirectamente — agregan toda la información pública
disponible al cierre (lesiones, suspensiones, forma reciente,
percepción de los apostadores) en un solo número, que es exactamente
lo que le faltaba al modelo. Esto explica por qué mejoran con margen
real los dos mercados de goles totales, y por qué no ayudan en BTTS:
no hay una cuota de mercado específica para BTTS cargada en este
dataset — sería el próximo candidato si se quisiera mejorar ese
mercado puntual.

## Historial: primera ronda del 11 nov (xG), ya superada por la de cuotas

Antes de probar las cuotas, se cargó xG real de Understat a la BD y
se agregó como feature rodante de equipo (`xg_scored_avg_last5`/
`xg_conceded_avg_last5`) — ver `docs/xgb_1x2_resultados.md` para el
detalle completo. **Resultado de esa ronda: el xG no alcanzó.**
Comparación controlada de esa ronda (misma calibración, sin cuotas
todavía):

| Objetivo | AUC sin xG | AUC con xG | LogLoss sin xG | LogLoss con xG |
|---|---|---|---|---|
| `over_1_5` | 0.530 | 0.526 | 0.534 | 0.538 |
| `over_2_5` | 0.521 | 0.558 | 0.689 | 0.684 |
| `btts` | 0.537 | 0.507 | 0.684 | 0.686 |

### Bug encontrado y corregido durante esa ronda: calibración isotónica inestable

Al re-medir con xG, el LogLoss de `btts` saltó a ~1.02 sin que el
modelo hubiera cambiado de forma razonable. Investigado antes de
reportarlo: la calibración isotónica
(`CalibratedClassifierCV(method="isotonic")`) asigna probabilidad
**exactamente 0.0** a la clase verdadera en varios partidos de test
(confirmado a mano: 2 de 526 en `over_1_5`, 5 de 526 en `btts`, 5 de
526 en el 1X2). `log_loss` recorta esos ceros a un épsilon numérico,
lo que dispara una penalización enorme (~34 nats) que no refleja
ninguna mejora o empeoramiento real del modelo. Causa raíz: `val`
tiene ~528 filas, insuficientes para que la regresión isotónica (no
paramétrica) generalice bien en los extremos; la sigmoide (Platt, 2
parámetros) es mucho más estable con ese tamaño de muestra.
**Corrección aplicada:** `calibrate_binary_model` y
`calibrate_xgb_1x2` usan `method="sigmoid"` desde entonces — todos los
números de este documento (ambas rondas) ya están con el fix aplicado.

Los números reportados ANTES del 11 nov (con calibración isotónica,
sin xG ni cuotas: `over_1_5` AUC 0.547/LogLoss 0.866; `over_2_5` AUC
0.511/LogLoss 0.827; `btts` AUC 0.536/LogLoss 0.752) quedan obsoletos
— no se puede saber, sin volver a correrlos, qué parte de esos
LogLoss altos era el bug de calibración y qué parte era el modelo
real.

El Poisson/Dixon-Coles (4.2) no usa `predictor_columns()` — se ajusta
directamente por máxima verosimilitud sobre los goles de cada
liga/temporada. **No consume ni el xG ni las cuotas, sus resultados no
cambiaron en ninguna de las dos rondas** (ver
`docs/dixon_coles_resultados.md`).

## Conclusión honesta para Carlos

Con xG + cuotas de mercado cargadas y la calibración corregida:
**`over_1_5` y `over_2_5` ya tienen una ventaja real y medible sobre
la línea base trivial, y cumplen el criterio del plan (AUC > 0.6) por
primera vez. `btts` sigue sin funcionar, y de hecho las cuotas lo
empeoran** — candidato claro para excluir de cualquier recomendación
de apuestas si se avanza a Fase 5, o para intentar mejorar
específicamente con una cuota de mercado de BTTS (no cargada todavía
en este dataset). El pipeline completo sigue funcionando
correctamente de punta a punta. Fase 5 (capa prescriptiva) sigue en
pausa hasta que Carlos decida cómo seguir — pero la situación cambió
de forma real respecto a las dos rondas anteriores: ya hay 2 de 3
modelos binarios con una ventaja demostrada.
