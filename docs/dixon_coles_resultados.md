# Resultados del modelo Poisson/Dixon-Coles (tarea 4.2)

Sustituye al "notebook" que pedía el plan arquitectónico original —
este proyecto no usa Jupyter en ningún otro lado (ver `AGENTS.md`), así
que se documenta el mismo ejemplo real en Markdown en vez de introducir
una herramienta nueva solo para esta tarea.

Corrida real contra el dataset consolidado completo
(`src/futbol/features/dataset.py`), split temporal 70/15/15
(`src/futbol/models/split.py`), un modelo Dixon-Coles independiente
por cada `(league_code, season_code)` (`src/futbol/models/poisson_dixon_coles.py`).

## Evaluación en TEST (criterio de aceptación del plan: RPS < 0.25)

| Liga | Temporada | Partidos train | Partidos test | RPS | RPS trivial* | Brier |
|---|---|---|---|---|---|---|
| ENG-Premier League | 2526 | 152 | 100 | 0.231 | 0.223 | 0.681 |
| ESP-La Liga | 2526 | 155 | 124 | 0.218 | 0.220 | 0.612 |
| FRA-Ligue 1 | 2526 | 136 | 95 | 0.238 | 0.236 | 0.703 |
| GER-Bundesliga | 2526 | 122 | 93 | 0.212 | 0.239 | 0.619 |
| ITA-Serie A | 2526 | 142 | 114 | 0.226 | 0.239 | 0.642 |

\* RPS trivial = predecir siempre la proporción histórica H/D/A de
`train` para todos los partidos de test, sin ningún modelo — ver nota
de corrección más abajo.

**Las 5 ligas cumplen el número exacto del criterio de aceptación (RPS
< 0.25 en test) — pero eso por sí solo no demuestra que el modelo
aporte algo.**

**Corrección honesta agregada el 11 nov, al encontrar el mismo problema
en la tarea 4.4**: comparado contra la línea base trivial, el modelo
gana con claridad en GER-Bundesliga e ITA-Serie A, es prácticamente
indistinguible de la trivial en ESP-La Liga, y queda ligeramente PEOR
que la trivial en ENG-Premier League y FRA-Ligue 1. Un resultado
mixto, no el "aprueba las 5 ligas" que parecía al mirar solo el número
absoluto sin comparar contra nada — ver `docs/xgb_binary_resultados.md`
para el detalle completo y la recomendación antes de seguir a Fase 5.

La temporada **2425** de las 5 ligas no aparece en esta tabla: cae
entera dentro del split de entrenamiento (terminó antes del corte
temporal global), así que no hay partidos futuros reales contra los
que evaluarla — `fit_and_evaluate_by_group` devuelve `NaN` para esos
casos en vez de inventar una métrica. No es un error, es una propiedad
real de qué tan reciente es cada temporada respecto a hoy — ver
`INFORME_PROYECTO.md`.

## Ejemplo real: ratings de ENG-Premier League 2425 (entrenado con sus 380 partidos)

Top 5 por parámetro de ataque:

| Equipo | Ataque | Defensa |
|---|---|---|
| Liverpool FC | 0.458 | 0.035 |
| Manchester City | 0.285 | 0.094 |
| Arsenal | 0.231 | −0.170 |
| Newcastle United | 0.228 | 0.155 |
| Brighton & Hove Albion | 0.213 | 0.385 |

Últimos 3:

| Equipo | Ataque | Defensa |
|---|---|---|
| Ipswich Town | −0.377 | 0.685 |
| Leicester City | −0.466 | 0.655 |
| Southampton | −0.698 | 0.723 |

**Verificación contra la realidad** (no es una coincidencia menor):
Liverpool FC fue el campeón real de la Premier League 2024-25, y
Southampton/Leicester City/Ipswich Town fueron exactamente los 3
equipos que descendieron esa temporada — el modelo, sin saber nada de
la tabla de posiciones, les da por lejos los peores parámetros de
ataque y defensa de la liga, usando solo resultados de partidos.

`home_advantage` = 0.063 (equivale a ≈6.5% más goles esperados de
local, en escala multiplicativa `exp(0.063)`) — más bajo que las
cifras clásicas de la literatura de Dixon-Coles (~30-40%), consistente
con la tendencia documentada de ventaja de local reducida en el fútbol
reciente. `rho` = −0.034 (pequeño, cerca de cero, dentro del rango
esperable).

Ejemplo de predicción: Liverpool FC (local) vs. Manchester City →
P(gana Liverpool) = 0.483, P(empate) = 0.233, P(gana City) = 0.283.

## Decisiones de diseño (no pedidas explícitamente por el plan, pero necesarias)

- **Un modelo por `(liga, temporada)`**, no uno global ni uno por liga
  que mezcle temporadas — los equipos de distinta liga nunca juegan
  entre sí en este dataset, y mezclar temporadas distintas de la misma
  liga ignoraría que los planteles cambian (ascensos/descensos,
  fichajes). Alcance reducido a propósito: sin ponderación por
  recencia dentro de una misma temporada (el Dixon-Coles original la
  usa); se deja para una iteración futura si hace falta.
- **La verosimilitud se vectorizó con NumPy** (sin loop en Python por
  partido): la primera versión, con un loop simple, tardaba minutos
  por cada ajuste liga/temporada (medido corriendo contra los datos
  reales) — vectorizada, un ajuste de ~380 partidos tarda ~0.2
  segundos. Necesario para que ajustar los 10 grupos (5 ligas × 2
  temporadas) sea práctico, hoy y en una futura Fase 6 donde el
  pipeline reentrena seguido.
