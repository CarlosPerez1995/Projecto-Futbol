# Resultados del modelo de clasificación 1X2 con XGBoost (tarea 4.3)

**Actualizado el 11 nov** tras cargar xG real a la BD y volver a medir
(decisión de Carlos) — ver `docs/xgb_binary_resultados.md` para el
detalle completo del bug de calibración encontrado en esta remedición
y la comparación controlada con/sin xG. Resumen de lo que cambia acá:
el xG mejora el LogLoss de este modelo de forma marginal (1.076 →
1.073, calibración sigmoide en ambos casos) — sigue sin haber una
ventaja clara sobre la línea base trivial.

Corrida real contra el dataset consolidado completo (3.515 partidos),
split 70/15/15 (`train`=2.461 / `val`=528 / `test`=526) — mismo split
que antes de cargar xG, el pendiente no agregó partidos nuevos.

## Resultado en TEST (con xG, calibración sigmoide — ver nota de corrección abajo)

| Métrica | Valor real | Criterio del plan | ¿Cumple? |
|---|---|---|---|
| LogLoss | 1.073 | < 1.1 | Sí, el número — ver nota sobre qué tan significativo es |
| Brier (ver nota de convención abajo) | 0.647 | < 0.35 | Depende de la convención, ver abajo |

LogLoss trivial (predecir siempre la proporción H/D/A de `train` para
todo `test`) = **1.078**. El modelo (1.073) queda apenas mejor que la
trivial — una diferencia de 0.005, dentro de lo que podría ser ruido
de una sola corrida de test con 526 partidos. No es la ventaja
contundente que haría falta para confiar en el modelo sobre simplemente
conocer las proporciones históricas de local/empate/visitante.

## Corrección importante: bug de calibración isotónica, encontrado al re-medir con xG

Al re-medir con xG, el LogLoss de este modelo saltó a 1.407 usando la
calibración isotónica original del plan — mucho peor que el 1.090 que
se había reportado antes (sin xG). Investigado antes de reportarlo
como "el resultado real": la isotónica asigna probabilidad
**exactamente 0.0** a la clase verdadera en 5 de los 526 partidos de
test; `log_loss` recorta esos ceros a un épsilon numérico, lo que
dispara una penalización gigante (~34 nats cada uno) que no tiene
nada que ver con que el modelo haya empeorado. Causa: `val` tiene solo
~528 filas repartidas en 3 clases (one-vs-rest dentro de
`CalibratedClassifierCV`), insuficiente para que una regresión
isotónica (no paramétrica) generalice bien en los extremos — la
sigmoide (Platt, 2 parámetros) es mucho más robusta con ese tamaño de
muestra. Se comparó sin calibrar (1.077), isotónica (1.407, rota) y
sigmoide (1.073) antes de decidir el cambio. **Se corrigió el código**
(`calibrate_xgb_1x2`, ahora `method="sigmoid"`) — ver también
`docs/xgb_binary_resultados.md`, que tiene el mismo bug y la misma
corrección para los 3 modelos binarios.

Esto implica que el número reportado anteriormente (1.090, con
isotónica) para la corrida SIN xG también estaba potencialmente
afectado por este mismo bug, en menor grado. La comparación limpia
antes/después de xG, con la misma calibración (sigmoide) en ambos
lados, es: **sin xG = 1.076, con xG = 1.073** — una mejora de 0.003,
no significativa.

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
deportiva), el número de este modelo sería `0.647 / 3 ≈ 0.216` — que
SÍ cumpliría el 0.35. No se cambió la fórmula ya usada para "hacer
pasar" el número: se deja reportado el valor real bajo la definición
documentada, con esta nota explícita.

## Importancia de features (top 8, modelo base antes de calibrar, con xG)

| Feature | Importancia |
|---|---|
| `current_streak_result_away` | 0.112 |
| `xg_scored_avg_last5_home` | 0.094 |
| `form_points_avg_last5_home` | 0.087 |
| `xg_scored_avg_last5_away` | 0.081 |
| `form_points_avg_last5_away` | 0.066 |
| `xg_conceded_avg_last5_home` | 0.065 |
| `clean_sheets_rate_last5_away` | 0.052 |
| `xg_conceded_avg_last5_away` | 0.049 |

Las 4 features nuevas de xG entran entre las 8 más importantes del
modelo (el árbol sí las usa para dividir), pero eso no se traduce en
una mejora medible del LogLoss en test — son útiles para que el
modelo "explique" mejor el `train` (añaden información que antes no
tenía), pero no generalizan a una ventaja real sobre la trivial en
datos nuevos. Mismo patrón que ya se documentó para las features de
forma de la Fase 3: el modelo encuentra *algo* en `train`, pero eso no
necesariamente mejora `test`.

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
- **Calibración sigmoide (Platt), no isotónica** (cambiado el 11 nov,
  ver sección dedicada arriba) — la isotónica es inestable con un
  `val` de este tamaño (~528 filas).
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
