# Resultados del modelo de clasificación 1X2 con XGBoost (tarea 4.3)

Corrida real contra el dataset consolidado completo (3.515 partidos),
split 70/15/15 (`train`=2.461 / `val`=528 / `test`=526).

## Resultado en TEST

| Métrica | Valor real | Criterio del plan | ¿Cumple? |
|---|---|---|---|
| LogLoss | 1.090 | < 1.1 | Sí, el número exacto — ver corrección abajo |
| Brier (ver nota de convención abajo) | 0.658 | < 0.35 | Depende de la convención, ver abajo |

## Corrección honesta agregada el 11 nov (al encontrar el mismo problema en la tarea 4.4)

El LogLoss de un modelo trivial que predice siempre la proporción
histórica de `train` (H/D/A) para todos los partidos de test, sin
ningún modelo, es **1.078** — **el modelo de XGBoost (1.090) queda
ligeramente PEOR que esa trivial.** Cumple el número exacto que pedía
el plan, pero ese número por sí solo no demuestra que el modelo aporte
algo por encima de simplemente conocer las proporciones históricas de
local/empate/visitante. Comparado sin calibrar (1.081) y calibrado con
sigmoide/Platt en vez de isotónica (1.076), el resultado es
prácticamente el mismo — no es un problema de la calibración, el
modelo base ya no logra generalizar mejor que la trivial desde `train`
(LogLoss 0.962) hacia `val`/`test` (~1.05-1.09). Ver
`docs/xgb_binary_resultados.md` para el diagnóstico completo y la
recomendación antes de seguir a Fase 5.

## Nota honesta sobre el Brier Score: posible ambigüedad del plan original

El Brier multiclase se implementó con la definición original de Brier
(1950): para cada partido, la suma (no el promedio) de `(p_clase −
o_clase)²` sobre las 3 clases (H/D/A) — rango posible `[0, 2]`. Es la
MISMA convención que ya se usó en `docs/dixon_coles_resultados.md`
para el modelo Poisson/Dixon-Coles (ahí dio 0.58-0.70, en el mismo
rango que acá) — los dos modelos se midieron con la misma vara, se
pueden comparar entre sí sin problema.

El plan arquitectónico original pedía "Brier < 0.35" sin especificar
la fórmula exacta. Si en cambio se promedia esa suma entre las 3
clases (otra convención común en la literatura de predicción
deportiva), el número de este modelo sería `0.658 / 3 ≈ 0.219` — que
SÍ cumpliría el 0.35. No se cambió la fórmula ya usada para "hacer
pasar" el número: se deja reportado el valor real bajo la definición
documentada, con esta nota explícita, para que quien revise pueda
juzgar con la información completa en vez de una cifra sin contexto.
**LogLoss, que no tiene esta ambigüedad, sí cumple el criterio con
margen (1.090 contra el límite de 1.1).**

## Importancia de features (top 5, modelo base antes de calibrar)

| Feature | Importancia |
|---|---|
| `form_points_avg_last5_home` | 0.146 |
| `goals_scored_avg_last5_away` | 0.096 |
| `goals_scored_avg_last5_home` | 0.080 |
| `matches_played_before_home` | 0.063 |
| `goals_conceded_avg_last5_home` | 0.062 |

Tiene sentido futbolístico: la forma reciente en puntos y los goles a
favor (local y visitante) son las señales más fuertes — ninguna
feature "rara" domina por accidente.

## Decisiones de diseño (no pedidas explícitamente por el plan, pero necesarias)

- **Un solo modelo global**, no uno por liga como el Dixon-Coles —
  XGBoost aprende patrones de forma relativa (promedios, rachas) que
  generalizan razonablemente entre ligas; a diferencia del modelo
  estadístico, acá no hay un parámetro explícito por equipo que
  tendría que vivir dentro de una sola liga. No se incluyó
  `league_code` como feature categórica en esta primera versión —
  queda como posible mejora futura si hiciera falta más poder
  predictivo por liga.
- **Validación cruzada con `TimeSeriesSplit`, no k-fold al azar**: la
  búsqueda de hiperparámetros (`GridSearchCV`) usa folds que respetan
  el orden temporal — mezclar al azar en series de tiempo es otra
  forma de fuga de datos.
- **Calibración con el split `val`, nunca `train`**: calibrar con los
  mismos datos que ya vio el modelo al ajustarse daría una calibración
  artificialmente optimista.
- **`current_streak_result` (texto `W`/`D`/`L`) se codifica a escala
  ordinal simple** (`W`=1, `D`=0, `L`=−1) antes de entrenar — XGBoost
  en esta versión no acepta columnas de texto directo sin configurar
  soporte de categóricas, y una escala ordinal es una representación
  razonable para algo que ya es inherentemente "mejor/neutral/peor".
- **`result_1x2` se codifica con `LabelEncoder`** (orden alfabético
  `A`/`D`/`H`) — verificado que XGBoost 3.4.1 rechaza etiquetas de
  texto directo (`ValueError` probado a propósito antes de escribir el
  código final, no asumido).
- **API de calibración verificada contra el código instalado, no
  asumida de memoria**: `CalibratedClassifierCV(cv="prefit")` ya no
  existe en esta versión de scikit-learn (1.9.1); el reemplazo vigente
  es `CalibratedClassifierCV(FrozenEstimator(modelo))`.
