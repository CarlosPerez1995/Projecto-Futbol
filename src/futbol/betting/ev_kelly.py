"""Valor esperado y Kelly fraccionado (tarea 5.1, Fase 5).

Fórmulas estándar de apuestas deportivas, aplicadas sobre la
probabilidad CALIBRADA del modelo (no la del mercado) y la cuota
decimal real ofrecida (ej. 2.00 = la ganancia neta es igual al monto
apostado).

**Advertencia central, verificada antes de recomendar nada real** (ver
``docs/backtest_resultados.md``): los modelos de Fase 4 que superan la
línea base trivial lo hacen en gran parte porque usan la probabilidad
implícita de la propia cuota de mercado como feature (~48% de la
importancia en el modelo 1X2, ver ``docs/xgb_1x2_resultados.md``).
Apostar con una probabilidad igual a la del mercado (ya sin el margen
de la casa, "devigged") da, por construcción matemática, un valor
esperado negativo exacto: si ``p = p_devigged``, entonces
``EV = p_devigged * cuota - 1 = 1/overround - 1 < 0`` — es exactamente
el margen de la casa, no hay forma de evitarlo apostando con esa misma
probabilidad. El valor real de una apuesta solo existe cuando la
probabilidad CALIBRADA del modelo se aparta de la del mercado lo
suficiente como para superar ese margen — no alcanza con que el
modelo "le gane a la trivial" en LogLoss/AUC, que mide calidad de
calibración, no rentabilidad de apostar.
"""
from __future__ import annotations


def expected_value(prob: float, decimal_odds: float) -> float:
    """Valor esperado por unidad apostada: ``prob * cuota - 1``.
    Positivo = ventaja teórica según el modelo; negativo o cero = sin
    ventaja, no apostar.
    """
    return prob * decimal_odds - 1.0


def kelly_fraction(prob: float, decimal_odds: float) -> float:
    """Fracción óptima del banco según el criterio de Kelly completo:
    ``(p * cuota - 1) / (cuota - 1)``. Nunca negativa — se recorta a 0
    si el valor esperado es negativo (no tiene sentido práctico
    devolver una fracción negativa en este contexto, nunca se "apuesta
    al revés" solo por el resultado de esta fórmula).
    """
    if decimal_odds <= 1.0:
        return 0.0
    f = (prob * decimal_odds - 1.0) / (decimal_odds - 1.0)
    return max(0.0, f)


def fractional_kelly(
    prob: float,
    decimal_odds: float,
    kelly_multiplier: float = 0.5,
    max_fraction: float = 0.05,
) -> float:
    """Kelly fraccionado: ``kelly_fraction() * kelly_multiplier``,
    acotado a ``max_fraction`` del banco.

    Kelly completo asume que la probabilidad del modelo es exacta —
    en la práctica nunca lo es (viene de un modelo calibrado con datos
    limitados), así que apostar Kelly completo sobreexpone el banco a
    errores de calibración. Mitad de Kelly (``kelly_multiplier=0.5``,
    valor por defecto) es la convención más común en la literatura de
    apuestas deportivas por ese motivo — decisión de diseño de este
    proyecto, no pedida explícitamente por el plan original.
    ``max_fraction`` es un tope duro adicional: ninguna apuesta
    individual, sin importar cuánta ventaja teórica tenga, debe poner
    en riesgo más de ese % del banco de una sola vez.
    """
    f = kelly_fraction(prob, decimal_odds) * kelly_multiplier
    return min(f, max_fraction)
