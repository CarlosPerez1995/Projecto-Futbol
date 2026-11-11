# Pendientes del proyecto — Fútbol

*Última actualización: 11 nov 2026. Complementa a `INFORME_PROYECTO.md`
(qué está hecho) — acá va solo lo que falta y de quién depende.*

## Bloqueante activo — decisión de Carlos

**Cómo seguir en Fase 4, tras cargar xG y volver a medir (11 nov,
resultado real reportado a Carlos)**: ya se cargó el xG real de
Understat a la BD (`matches.home_xg`/`away_xg`) y se agregaron
features de xG rodante por equipo (`xg_scored_avg_last5`,
`xg_conceded_avg_last5`, mismo patrón sin fuga que las de goles) — era
el candidato más directo para que los modelos superaran la línea
base trivial. **Resultado real: no lo logra.** Comparación controlada
(misma calibración antes/después, para no mezclar con un bug de
calibración encontrado en el camino — ver `docs/xgb_binary_resultados.md`):
el 1X2 mejora 0.003 en LogLoss (ruido), `over_2_5` mejora algo en AUC
(+0.037) pero sigue sin cruzar el umbral del plan (>0.6), los otros
dos no mejoran. El pipeline completo sigue funcionando correctamente
— lo que falta no es un bug ni la ausencia de xG, es una señal
predictiva más fuerte que un promedio de 5 partidos (de goles o de xG)
por equipo.

**Camino pendiente de que Carlos decida, ahora con el xG ya
descartado como solución fácil**:
1. Seguir a Fase 5 (capa prescriptiva — decisiones de apuestas) de
   todos modos, sabiendo las salvedades (ningún modelo demuestra edge
   claro y consistente).
2. Buscar otra señal predictiva más fuerte antes de seguir (ej.
   alineaciones probables, lesiones, cuotas de mercado como feature —
   las cuotas ya están en la BD desde Fase 2 pero no se usan como
   predictoras todavía).
3. Pausar Fase 4/5 del todo y reorientar el proyecto.

Construir una capa de apuestas reales sobre modelos sin edge
demostrado sería irresponsable, así que **Fase 5 sigue en pausa**
hasta esta decisión — ver `PLAN_DE_TRABAJO.md`.

## Resueltos recientemente

- **xG cargado y re-medido (11 nov)**: decisión de Carlos, ejecutada y
  reportada — ver bloqueante arriba y `docs/xgb_1x2_resultados.md` /
  `docs/xgb_binary_resultados.md` para el detalle completo (incluye un
  bug de calibración isotónica encontrado y corregido en el camino).
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

Fase 5 (capa prescriptiva, en pausa — ver bloqueante arriba) y Fase 6
(operación diaria) no tienen una sola línea de código todavía. Fase 4
(modelos predictivos) tiene 4 de 5 tareas hechas (falta el
backtesting, también en pausa por el mismo motivo). Detalle de qué
incluye cada una, en qué orden, y qué decisiones hace falta tomar en
el camino: ver `PLAN_DE_TRABAJO.md`.
