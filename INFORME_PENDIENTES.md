# Pendientes del proyecto — Fútbol

*Última actualización: 11 nov 2026. Complementa a `INFORME_PROYECTO.md`
(qué está hecho) — acá va solo lo que falta y de quién depende.*

## Sin bloqueantes activos hoy

**Resuelto (11 nov):** F9 — Carlos autorizó instalar
`scikit-learn`/`scipy`/`xgboost`/`joblib`, ya instaladas y congeladas
en `requirements.txt`. Fase 4 (modelos predictivos) arrancada, tarea
4.1 (split temporal) hecha — ver `PLAN_DE_TRABAJO.md` para lo que sigue
dentro de la fase (4.2-4.5, sin decisiones pendientes de Carlos en el
camino inmediato).

## Alcance reducido a propósito (documentado, no bloquea nada)

Quedó fuera a propósito al cerrar fases 2 y 3, para no demorar el resto
del trabajo con algo que no era indispensable todavía. No la está
esperando nadie activamente — se retoma cuando convenga, probablemente
dentro de Fase 4 si hace falta más poder predictivo.

| Qué | De quién depende | Detalle |
|---|---|---|
| Cargar xG (gol esperado, de Understat) a la base de datos | Jefe de proyecto, cuando se priorice | Understat ya se usa para identidad de equipos/partidos, pero sus columnas de xG nunca se cargaron a la BD. Las features de partido (`home_xg`/`away_xg`) están ahí pero vacías, documentado en `docs/features_map.txt`. |

**Resuelto (10 nov):** cuotas de mercados over/under 2.5 y hándicap
asiático — ya implementadas (`load_odds_extra_markets`), primera tarea
real delegada a OpenCode como operativo (ver `AGENTS.md`, sección
"OpenCode como operativo"), spec del jefe de proyecto, verificada a
mano contra el CSV real antes de mergear. Sale de esta lista.

## Housekeeping sin resolver (viejo, de antes de la pausa de agosto)

| Qué | De quién depende | Detalle |
|---|---|---|
| Carpeta `~/Escritorio/proyectos` redundante con el remoto de este repo | Carlos (decisión de limpieza de carpetas, no es código) | Señalado desde el reporte del 5 oct, nunca se verificó de nuevo ni se resolvió. No afecta el funcionamiento del proyecto, solo es orden de carpetas en la máquina. |
| `H5` del hub — elegir herramientas y anotarlas en `HERRAMIENTAS.md` | Jefe de proyecto | Pendiente genérico del hub, no específico de una tarea de este repo. OpenCode ya está activado como operativo acá (ver arriba), falta solo dejarlo anotado en `HERRAMIENTAS.md` del hub. |

## Fases completas sin empezar

Fase 4 (modelos predictivos), Fase 5 (capa prescriptiva) y Fase 6
(operación diaria) — ninguna tiene una sola línea de código todavía.
Detalle de qué incluye cada una, en qué orden, y qué decisiones hace
falta tomar en el camino: ver `PLAN_DE_TRABAJO.md`.
