# Resultados del modelo de clasificación 1X2 con XGBoost (tarea 4.3)

**Actualizado el 11 nov, segunda ronda del día**: tras agregar las
probabilidades implícitas de la cuota de cierre de mercado como
feature (decisión de Carlos), el LogLoss mejora de forma real: 1.073
→ **1.037**, ahora con un margen claro (0.041) sobre la línea base
trivial (1.078) — a diferencia de la ronda anterior (solo xG), donde
la mejora era de 0.003 y no significativa. Ver
`docs/xgb_binary_resultados.md` para el detalle completo de ambas
rondas, el bug de calibración encontrado en la primera, y por qué las
cuotas ayudan tanto.

Corrida real contra el dataset consolidado completo (3.515 partidos),
split 70/15/15 (`train`=2.461 / `val`=528 / `test`=526) — mismo split
en las 3 corridas (sin features nuevas, con xG, con xG+cuotas): ningún
pendiente agregó partidos nuevos.

## Resultado en TEST (con xG + cuotas de mercado, calibración sigmoide)

| Métrica | Valor real | Criterio del plan | ¿Cumple? |
|---|---|---|---|
| LogLoss | 1.037 | < 1.1 | Sí, y con margen real sobre la trivial (ver abajo) |
| Brier (ver nota de convención abajo) | 0.620 | < 0.35 | Depende de la convención, ver abajo |

LogLoss trivial (predecir siempre la proporción H/D/A de `train` para
todo `test`) = **1.078**. El modelo (1.037) le gana por 0.041 — a
diferencia de las dos corridas anteriores (sin xG: 1.076; con xG sin
cuotas: 1.073), ambas dentro de lo que podía ser ruido, esta diferencia
ya es sustancial para un test de 526 partidos.

## Historial: por qué el xG solo no alcanzaba (primera ronda del 11 nov)

Al re-medir por primera vez ese día (solo con xG, antes de probar las
cuotas) se encontró y corrigió un bug real de calibración isotónica
(`CalibratedClassifierCV(method="isotonic")` asignaba probabilidad
exacta 0.0 a la clase verdadera en varios partidos de test con un
`val` de solo ~528 filas — detalle completo en
`docs/xgb_binary_resultados.md`). Corregido a `method="sigmoid"`. Con
esa corrección, la comparación limpia sin cuotas fue: sin xG = 1.076,
con xG = 1.073 — una mejora de 0.003, no significativa. El salto real
vino de las cuotas, no del xG.

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
deportiva), el número de este modelo sería `0.620 / 3 ≈ 0.207` — que
SÍ cumpliría el 0.35. No se cambió la fórmula ya usada para "hacer
pasar" el número: se deja reportado el valor real bajo la definición
documentada, con esta nota explícita.

## Importancia de features (top 8, modelo base antes de calibrar, con xG + cuotas)

| Feature | Importancia |
|---|---|
| `odds_implied_prob_home` | 0.204 |
| `odds_implied_prob_away` | 0.165 |
| `odds_implied_prob_draw` | 0.062 |
| `odds_implied_prob_over_2_5` | 0.052 |
| `matches_played_before_home` | 0.038 |
| `form_points_avg_last5_home` | 0.037 |
| `matches_played_before_away` | 0.034 |
| `xg_scored_avg_last5_home` | 0.034 |

Diferencia clara con la ronda anterior (donde `current_streak_result`/
`form_points`/`xg_*` dominaban, ~0.09-0.11 cada una): ahora las 4
columnas de cuotas juntas acaparan cerca de la mitad de la importancia
total (0.20+0.17+0.06+0.05 ≈ 0.48) — el modelo encontró que la
probabilidad implícita del mercado es, por lejos, la señal más fuerte
disponible, más que cualquier combinación de features de forma propia
calculadas desde cero. Tiene sentido: el mercado agrega información que
ningún promedio de partidos anteriores puede capturar (lesiones,
suspensiones, contexto puntual del partido).

## Decisiones de diseño (no pedidas explícitamente por el plan, pero necesarias)

- **Un solo modelo global**, no uno por liga como el Dixon-Coles —
  XGBoost aprende patrones de forma relativa (promedios, rachas,
  probabilidades de mercado) que generalizan razonablemente entre
  ligas; a diferencia del modelo estadístico, acá no hay un parámetro
  explícito por equipo que tendría que vivir dentro de una sola liga.
  No se incluyó `league_code` como feature categórica en esta primera
  versión — queda como posible mejora futura si hiciera falta más
  poder predictivo por liga.
- **Validación cruzada con `TimeSeriesSplit`, no k-fold al azar**: la
  búsqueda de hiperparámetros (`GridSearchCV`) usa folds que respetan
  el orden temporal — mezclar al azar en series de tiempo es otra
  forma de fuga de datos.
- **Calibración con el split `val`, nunca `train`**: calibrar con los
  mismos datos que ya vio el modelo al ajustarse daría una calibración
  artificialmente optimista.
- **Calibración sigmoide (Platt), no isotónica** (cambiado el 11 nov,
  ver sección histórica arriba) — la isotónica es inestable con un
  `val` de este tamaño (~528 filas).
- **Cuota de cierre promedio (`bookmaker='avg'`), no de una casa
  puntual** (agregado el 11 nov, ver `docs/features/odds.py` /
  `docs/odds_columns_map.md`) — es la única columna de cuotas con
  cobertura estable entre temporadas, el esquema por casa cambia.
  Probabilidad implícita calculada con "devigging" (`1/cuota`
  normalizado para que la suma dé 1), no la cuota cruda — la cuota
  cruda incluye el margen de la casa, no es una probabilidad.
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
