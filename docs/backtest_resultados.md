# Backtesting histórico de apuestas (tarea 4.5 / arranque de Fase 5)

**Resumen corto, sin maquillar: la estrategia de "apostar cuando el
valor esperado del modelo sea positivo" (lo que pedía el plan para
Fase 5) pierde dinero de forma severa en el backtest real — 84% del
banco simulado en 1X2, 49% en over/under 2.5, usando cuotas reales de
cierre y el split `test` nunca visto en entrenamiento ni calibración.
No es un bug de código (verificado a fondo, ver abajo): es la
consecuencia directa de que el "edge" medido en Fase 4 (LogLoss/AUC
mejor que la línea base trivial) viene en gran parte de que el modelo
usa la propia cuota de mercado como feature — y esa ventaja NO se
traduce en ventaja real para apostar contra ese mismo mercado.**

## Qué se simuló

`src/futbol/betting/backtest.py` — para cada partido del split `test`
(526 partidos, nunca usados para entrenar ni calibrar ningún modelo):

1. Probabilidad calibrada del modelo para cada resultado posible
   (1X2: H/D/A: over/under 2.5: over/under).
2. Cuota REAL de cierre promedio (`bookmaker='avg'`, `is_closing=1`,
   la misma fuente ya usada como feature) — no cuotas hipotéticas.
3. Valor esperado = `prob_modelo * cuota - 1`
   (`futbol.betting.ev_kelly.expected_value`). Si es positivo, se
   aposta con Kelly fraccionado (mitad de Kelly, tope 5% del banco por
   apuesta — ver docstring de `ev_kelly.py` para por qué esos valores).
4. Banco inicial: 1.000 (unidades arbitrarias). Se actualiza apuesta
   por apuesta, en orden cronológico.

## Resultado real (umbral de EV > 0, el más permisivo — "cualquier valor esperado positivo cuenta")

| Mercado | Partidos con cuota | Apuestas hechas | Tasa de acierto | ROI | Banco final | Caída máxima |
|---|---|---|---|---|---|---|
| 1X2 | 522 | 520 | 30.0% | **-18.9%** | 157 (de 1.000) | -85.5% |
| over/under 2.5 | 522 | 275 | 37.8% | **-7.8%** | 511 (de 1.000) | -69.7% |

**Línea base trivial para esta comparación: no apostar nada, banco se
queda en 1.000 (0% de retorno).** Las dos estrategias quedan muy por
debajo de esa trivial — perder plata apostando es peor que no apostar.

## Se probó ser más selectivo (exigir más margen de EV) — no mejora de forma consistente

| Umbral de EV exigido | 1X2 ROI | over/under 2.5 ROI |
|---|---|---|
| > 0.00 | -18.9% | -7.8% |
| > 0.02 | -20.2% | -8.1% |
| > 0.05 | -16.4% | -6.3% |
| > 0.10 | -14.4% | **+0.02%** (casi exactamente cero, no una ventaja real) |
| > 0.15 | -7.1% | -2.1% |
| > 0.20 | -16.7% | -3.6% |

No hay una tendencia clara de mejora al exigir más margen — sube y
baja sin patrón, lo que es consistente con que las apuestas
"detectadas" sean ruido alrededor de cero, no una señal real que se
vuelve más confiable al filtrar más fuerte. Si hubiera una señal real,
subir el umbral debería mejorar el ROI de forma más o menos
consistente (quedarse solo con las mejores oportunidades); no es lo
que se observa.

## Verificación de que no es un bug: cuando el modelo discrepa del mercado, el mercado tenía razón

Se comparó la probabilidad del modelo contra la probabilidad implícita
del mercado (devigged, sin margen) para cada partido, y se separaron
los casos donde el modelo predice sensiblemente MÁS que el mercado de
los casos donde predice sensiblemente MENOS — y se midió la tasa real
de acierto en cada grupo:

**1X2 — resultado "H" (gana el local):**

| Grupo | n | Tasa real de H | Probabilidad del mercado en ese grupo |
|---|---|---|---|
| Modelo > mercado (+0.03 o más) | 81 | 44.4% | 48.9% |
| Modelo < mercado (-0.03 o más) | 243 | 43.2% | 41.1% |

**over/under 2.5 — resultado "over":**

| Grupo | n | Tasa real de over | Probabilidad del mercado en ese grupo |
|---|---|---|---|
| Modelo > mercado (+0.03 o más) | 153 | 43.1% | 45.0% |
| Modelo < mercado (-0.03 o más) | 132 | 63.6% | 65.0% |

**En las 4 filas, la probabilidad del MERCADO queda más cerca de lo
que realmente pasó que la del modelo.** Cuando el modelo se aparta del
mercado, el mercado tenía razón en apartarse menos — exactamente lo
opuesto de lo que haría falta para que divergir del mercado sea una
estrategia rentable. Esto no es una coincidencia de una sola corrida:
se repite en ambos modelos, en ambas direcciones de la divergencia.

También se verificó que el cálculo de valor esperado es aritméticamente
correcto contra ejemplos a mano (partido por partido, ver
`tests/test_betting_backtest.py` para el núcleo de la simulación, y
`tests/test_betting_ev_kelly.py` para las fórmulas) antes de concluir
que el resultado negativo es real y no un error de cómputo.

## Por qué pasa esto (ya anticipado antes de correr el backtest, ver `src/futbol/betting/ev_kelly.py`)

Los modelos de Fase 4 que superan la línea base trivial lo hacen en
gran parte porque usan la propia probabilidad implícita del mercado
como feature (~48% de la importancia en el modelo 1X2, ver
`docs/xgb_1x2_resultados.md`). Apostar con una probabilidad igual a la
del mercado da, por construcción matemática, un valor esperado
negativo exacto (el margen de la casa, ~6.5% de overround promedio
medido en este dataset). El modelo SÍ se aparta del mercado en una
fracción de los casos (el otro ~52% de las features, forma de equipo y
xG, meten algo de información adicional) — pero esa fracción de
apartamiento resulta ser, en promedio, ruido relativo a la verdad, no
señal: no hay evidencia de que el modelo "sepa algo que el mercado no
sabe" en la dirección correcta. Apostar cada vez que el modelo se
aparta del mercado termina siendo, en la práctica, pagar el margen de
la casa con alta frecuencia sin compensación.

## Qué NO se pudo backtestear: over/under 1.5

El modelo `xgb_over_1_5` (Fase 4) tiene una métrica decente (AUC
0.601, cruza el criterio del plan) — pero **este dataset no tiene
ninguna cuota de mercado real de over/under 1.5 cargada** (solo 1x2 y
over/under 2.5, ver `docs/odds_columns_map.md`). Sin una cuota real a
la que apostar, no se puede simular ni operar ese mercado todavía.
Dado el resultado de los otros dos mercados (donde sí había cuota),
no hay razón para esperar que cargar esa cuota cambiaría la
conclusión, pero queda sin verificar — pendiente si se quisiera
confirmarlo.

## Conclusión honesta para Carlos

**La Fase 5 tal como estaba planteada en el plan original ("apostar
cuando el EV sea positivo, con Kelly fraccionado") no es viable con
estos modelos, verificado con datos y cuotas reales — habría perdido
el 85% del banco simulado en el período de test.** El motivo de fondo
no es un error de implementación: es que el "edge" de Fase 4 (medido
contra una línea base trivial, en LogLoss/AUC) no es el mismo tipo de
edge que se necesita para apostar rentablemente contra el mercado que
generó buena parte de esa mejora. Esto no invalida el trabajo de Fase
4 — los modelos sí predicen mejor que la trivial — pero sí invalida la
idea de que eso alcance para construir un sistema de apuestas
automático tal como estaba planteado.

**Antes de seguir construyendo sobre Fase 5** (recomendaciones
diarias, registro de apuestas), hace falta que Carlos decida entre,
por ejemplo: (1) pausar Fase 5 del todo, (2) buscar una señal
genuinamente independiente del mercado (no solo forma histórica/xG,
que ya se probaron) antes de reintentar una estrategia de apuestas,
(3) usar los modelos solo como herramienta informativa (comparar la
opinión del modelo con la del mercado) sin automatizar apuestas de
dinero real, o (4) otra cosa. No se construyó el resto de Fase 5
(recomendaciones diarias, registro de apuestas) sobre una base que ya
se demostró perdedora en backtesting — sería repetir, a mayor escala,
el mismo error que este backtest existe justamente para evitar.
