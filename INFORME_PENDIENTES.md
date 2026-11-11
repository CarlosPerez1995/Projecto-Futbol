# Pendientes del proyecto — Fútbol

*Última actualización: 11 nov 2026. Complementa a `INFORME_PROYECTO.md`
(qué está hecho) — acá va solo lo que falta y de quién depende.*

## Bloqueante activo — decisión de Carlos

**Cómo seguir en Fase 5, tras construir y backtestear EV/Kelly el 11
nov (decisión previa de Carlos: avanzar con 1X2/over_1_5/over_2_5)**:
al simular con cuotas reales de cierre lo que habría pasado apostando
cada vez que el modelo calibrado ve valor esperado positivo
(`src/futbol/betting/backtest.py`), **el resultado real es una
pérdida severa**: -85% del banco simulado en 1X2, -49% en over/under
2.5 (`over_1_5` no se pudo backtestear, no hay cuota de mercado de ese
total cargada en este dataset). Verificado a fondo que no es un bug:
cuando el modelo discrepa de la cuota de mercado, la cuota de mercado
resulta ser más acertada que el modelo, en ambas direcciones y en
ambos mercados probados — ver `docs/backtest_resultados.md` para el
detalle completo, incluida la explicación matemática de por qué
(el edge de Fase 4 viene en gran parte de usar la propia cuota de
mercado como feature, y reproducir el mercado no da ventaja para
apostar contra él).

**No se construyeron las recomendaciones diarias ni el registro de
apuestas (puntos 2 y 3 de Fase 5)** sobre una estrategia que el propio
backtesting ya descartó — habría sido automatizar, a mayor escala, el
mismo error.

**Camino pendiente de que Carlos decida, con este hallazgo nuevo**:
1. Pausar Fase 5 del todo — el enfoque "EV + Kelly contra cuotas de
   mercado" tal como está planteado no funciona con estos modelos.
2. Buscar una señal genuinamente independiente del mercado (ni forma
   histórica ni xG, ya probados y en gran parte ya incorporados por el
   mercado mismo) antes de reintentar una estrategia de apuestas real.
3. Usar los modelos solo como herramienta informativa (comparar la
   opinión del modelo con la del mercado, sin apostar dinero real de
   forma automática).
4. Otra cosa.

**Fase 5 sigue en pausa** hasta esta decisión — ver
`PLAN_DE_TRABAJO.md`.

## Resueltos recientemente

- **Backtesting real de EV/Kelly (11 nov)**: decisión de Carlos
  ejecutada (avanzar a Fase 5) y backtesteada contra cuotas reales
  antes de construir nada más — resultado real: pérdida severa, ver
  bloqueante arriba y `docs/backtest_resultados.md`.
- **Cuotas de mercado como feature, resultado real (11 nov)**:
  decisión de Carlos, ejecutada y reportada —
  `docs/xgb_1x2_resultados.md` / `docs/xgb_binary_resultados.md`.
- **xG cargado y re-medido (11 nov)**: decisión de Carlos, ejecutada y
  reportada — no alcanzó por sí solo (ver historial en los mismos
  docs), pero de paso se encontró y corrigió un bug real de
  calibración isotónica inestable.
- **F9 (11 nov)**: Carlos autorizó instalar `scikit-learn`/`scipy`/
  `xgboost`/`joblib`, ya instaladas y congeladas en `requirements.txt`.
- **Mercados de cuotas over/under 2.5 y hándicap asiático (10 nov)**:
  ya implementadas (`load_odds_extra_markets`), primera tarea real
  delegada a OpenCode como operativo, verificada contra el CSV real
  antes de mergear.

## Housekeeping sin resolver (viejo, de antes de la pausa de agosto)

| Qué | De quién depende | Detalle |
|---|---|---|
| Carpeta `~/Escritorio/proyectos` redundante con el remoto de este repo | Carlos (decisión de limpieza de carpetas, no es código) | Señalado desde el reporte del 5 oct, nunca se verificó de nuevo ni se resolvió. No afecta el funcionamiento del proyecto, solo es orden de carpetas en la máquina. |
| `H5` del hub — elegir herramientas y anotarlas en `HERRAMIENTAS.md` | Jefe de proyecto | Pendiente genérico del hub, no específico de una tarea de este repo. OpenCode ya está activado como operativo acá (ver `AGENTS.md`), falta solo dejarlo anotado en `HERRAMIENTAS.md` del hub. |

## Fases completas sin empezar

Fase 4 (modelos predictivos) ya tiene sus 5 tareas hechas, incluido el
backtesting. Fase 5 (capa prescriptiva) tiene 1 de 3 tareas hechas
(EV/Kelly + backtest) pero bloqueada por el hallazgo de arriba — las
otras 2 (recomendaciones diarias, registro de apuestas) no se
construyeron a propósito. Fase 6 (operación diaria) no tiene una sola
línea de código todavía. Detalle de qué incluye cada una, en qué
orden, y qué decisiones hace falta tomar en el camino: ver
`PLAN_DE_TRABAJO.md`.
