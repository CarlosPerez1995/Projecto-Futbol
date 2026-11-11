# Pendientes del proyecto — Fútbol

*Última actualización: 11 nov 2026. Complementa a `INFORME_PROYECTO.md`
(qué está hecho) — acá va solo lo que falta y de quién depende.*

## Bloqueante activo — decisión de Carlos

**Cómo seguir en Fase 4, tras un hallazgo real del 11 nov**: los 3
modelos predictivos entrenados hasta ahora (Poisson/Dixon-Coles,
clasificación 1X2 y over/under/BTTS con XGBoost) no muestran una
ventaja clara y consistente por encima de una línea base trivial
(predecir siempre la tasa histórica). El código y el pipeline
funcionan correctamente (verificado con tests y a mano) — es la señal
de las features actuales la que no alcanza todavía, no un bug.
Detalle completo en `docs/xgb_binary_resultados.md`.

**Dos caminos, pendientes de que Carlos decida**:
1. Cargar xG (gol esperado) de Understat a la base de datos antes de
   seguir — candidato más directo para mejorar esto, especialmente
   para over/under y BTTS (ver fila de abajo, este trabajo ya estaba
   identificado, ahora tiene más urgencia).
2. Seguir a Fase 5 (capa prescriptiva — decisiones de apuestas) de
   todos modos, sabiendo las salvedades.

Construir una capa de apuestas reales sobre modelos sin edge
demostrado sería irresponsable, así que **Fase 5 queda en pausa**
hasta esta decisión — ver `PLAN_DE_TRABAJO.md`.

## Trabajo recomendado (ya no "cuando convenga")

| Qué | De quién depende | Detalle |
|---|---|---|
| Cargar xG (gol esperado, de Understat) a la base de datos | Jefe de proyecto, con la prioridad que le dé Carlos (ver bloqueante de arriba) | Understat ya se usa para identidad de equipos/partidos, pero sus columnas de xG nunca se cargaron a la BD. Las features de partido (`home_xg`/`away_xg`) están ahí pero vacías, documentado en `docs/features_map.txt`. Deja de ser un "nice to have": es el candidato más directo para que los modelos de Fase 4 superen la línea base trivial. |

## Resueltos recientemente

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
