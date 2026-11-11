# Pendientes del proyecto — Fútbol

*Última actualización: 11 nov 2026. Complementa a `INFORME_PROYECTO.md`
(qué está hecho) — acá va solo lo que falta y de quién depende.*

## Bloqueante activo — decisión de Carlos

**Cómo seguir en Fase 4, tras dos rondas de re-medición el 11 nov**:
primero se probó el xG (no alcanzó, ver abajo). Después, decisión de
Carlos: probar las cuotas de mercado (probabilidad implícita de la
cuota de cierre promedio, mercados 1x2 y over/under 2.5, ya cargados
desde Fase 2) como feature predictora. **Resultado real: esta sí
funciona.** El 1X2 le gana a la línea base trivial con margen real
(LogLoss 1.037 vs. 1.078 trivial), y `over_1_5`/`over_2_5` cruzan por
primera vez el criterio del plan (AUC > 0.6: 0.601 y 0.604). `btts`
sigue sin funcionar — y de hecho empeora con las cuotas (AUC 0.453,
peor que azar), porque no hay una cuota de mercado dedicada a BTTS en
este dataset. Detalle completo en `docs/xgb_1x2_resultados.md` /
`docs/xgb_binary_resultados.md`.

**Camino pendiente de que Carlos decida, con la situación ya
cambiada (2 de 3 modelos binarios con ventaja demostrada)**:
1. Avanzar a Fase 5 (capa prescriptiva) con `1X2`, `over_1_5` y
   `over_2_5`, excluyendo explícitamente `btts` hasta que tenga una
   señal propia.
2. Cargar también la cuota de mercado específica de BTTS (si
   `soccerdata`/football-data.co.uk la tiene disponible) antes de
   decidir sobre ese mercado puntual.
3. Pausar Fase 4/5 del todo de todos modos, por otro motivo (decisión
   de negocio, no técnica).

**Fase 5 sigue en pausa** hasta esta decisión — ver
`PLAN_DE_TRABAJO.md`.

## Resueltos recientemente

- **Cuotas de mercado como feature, resultado real (11 nov)**:
  decisión de Carlos, ejecutada y reportada — ver bloqueante arriba y
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

Fase 5 (capa prescriptiva, en pausa — ver bloqueante arriba) y Fase 6
(operación diaria) no tienen una sola línea de código todavía. Fase 4
(modelos predictivos) tiene 4 de 5 tareas hechas (falta el
backtesting, también en pausa por el mismo motivo). Detalle de qué
incluye cada una, en qué orden, y qué decisiones hace falta tomar en
el camino: ver `PLAN_DE_TRABAJO.md`.
