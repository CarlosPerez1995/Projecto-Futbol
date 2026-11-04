# Plan de trabajo — Fútbol

*Última actualización: 4 nov 2026. Qué sigue y en qué orden, a partir
de donde está hoy el proyecto (fases 0-3 completas, ver
`INFORME_PROYECTO.md`). Basado en el plan arquitectónico original
(`~/Escritorio/AuditoriaFutbol/Planes arquitectonicos/`, fuera de este
repo) ajustado con lo que realmente se construyó.*

## Antes de arrancar: F9 (Carlos)

Fase 4 necesita instalar `scikit-learn`, `scipy`, `xgboost` y `joblib`
— ninguno está en `requirements.txt` hoy. Por la regla del proyecto de
no agregar dependencias sin aprobación previa, esto se confirma una
sola vez, idealmente los 4 juntos en vez de uno por tarea, antes de
tocar código de Fase 4.

## Fase 4 — Modelos predictivos

Depende de Fase 3 (hecha). Orden sugerido, cada uno construido sobre
el anterior:

1. **Split temporal para backtesting** — dividir los partidos en
   entrenamiento/validación/prueba por fecha (70/15/15), nunca
   mezclado al azar (en series de tiempo, mezclar al azar es otra
   forma de fuga de datos: dejaría al modelo "aprender" de partidos
   futuros respecto a los que debe predecir).
2. **Modelo Poisson/Dixon-Coles** — el modelo estadístico clásico para
   fútbol: estima qué tan buen o mal equipo de ataque/defensa es cada
   uno, y con eso calcula la probabilidad de cada marcador posible.
3. **Modelo de clasificación 1X2** (XGBoost) — quién gana, pierde o
   empata, usando las features de forma de la Fase 3 como entrada.
   Cada versión del modelo se guarda con sus métricas y la referencia
   exacta a qué versión del dataset se entrenó (por eso `dataset.py`
   ya deja un hash en `features_spec.md`).
4. **Modelos de over/under y BTTS** — mismo patrón que el anterior,
   target distinto.
5. **Backtesting histórico** — simular, sobre partidos ya jugados que
   el modelo nunca vio en entrenamiento, qué tan rentable habría sido
   apostar siguiendo sus predicciones.

**Punto de decisión dentro de esta fase:** cuándo convenga, cargar el
xG de Understat a la base de datos (pendiente de Fase 2/3, ver
`INFORME_PENDIENTES.md`) puede mejorar estos modelos — no es
obligatorio para arrancar, pero es la ventana natural para retomarlo
si los primeros resultados sin xG no son suficientemente buenos.

## Fase 5 — Capa prescriptiva

Depende de Fase 4 (al menos un modelo con probabilidades calibradas).

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

- Cargar xG de Understat a la BD (ver Fase 4, punto de decisión).
- Sumar los mercados de cuotas over/under y hándicap asiático.
- Limpiar la carpeta `~/Escritorio/proyectos` redundante.

Ninguno de estos tres está bloqueando el avance de Fase 4 en adelante
— se insertan donde convenga según prioridad de Carlos.
