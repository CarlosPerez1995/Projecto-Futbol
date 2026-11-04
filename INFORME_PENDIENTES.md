# Pendientes del proyecto — Fútbol

*Última actualización: 4 nov 2026. Complementa a `INFORME_PROYECTO.md`
(qué está hecho) — acá va solo lo que falta y de quién depende.*

## Bloqueante activo

| Qué | De quién depende | Detalle |
|---|---|---|
| **F9 — instalar `scikit-learn`/`scipy`/`xgboost`/`joblib`** | **Carlos** | Fase 4 (modelos predictivos) no puede arrancar sin esto — regla del proyecto: no se agregan dependencias nuevas sin aprobación previa (`AGENTS.md`, regla 3). Es la única cosa que está deteniendo el avance hoy. |

## Alcance reducido a propósito (documentado, no bloquea nada)

Estas dos quedaron fuera a propósito al cerrar fases 2 y 3, para no
demorar el resto del trabajo con algo que no era indispensable todavía.
No las está esperando nadie activamente — se retoman cuando convenga,
probablemente dentro de Fase 4 si hace falta más poder predictivo.

| Qué | De quién depende | Detalle |
|---|---|---|
| Cargar xG (gol esperado, de Understat) a la base de datos | Jefe de proyecto, cuando se priorice | Understat ya se usa para identidad de equipos/partidos, pero sus columnas de xG nunca se cargaron a la BD. Las features de partido (`home_xg`/`away_xg`) están ahí pero vacías, documentado en `docs/features_map.txt`. |
| Cuotas de mercados over/under y hándicap asiático | Jefe de proyecto, cuando se priorice | Solo se implementó el mercado 1x2 (quién gana/pierde/empata). MatchHistory trae los otros dos, pero con un formato de columnas que cambia de temporada a temporada — se decidió no apurar ese diseño. |

## Housekeeping sin resolver (viejo, de antes de la pausa de agosto)

| Qué | De quién depende | Detalle |
|---|---|---|
| Carpeta `~/Escritorio/proyectos` redundante con el remoto de este repo | Carlos (decisión de limpieza de carpetas, no es código) | Señalado desde el reporte del 5 oct, nunca se verificó de nuevo ni se resolvió. No afecta el funcionamiento del proyecto, solo es orden de carpetas en la máquina. |
| `H5` del hub — elegir herramientas y anotarlas en `HERRAMIENTAS.md` | Jefe de proyecto | Pendiente genérico del hub, no específico de una tarea de este repo. OpenCode ya está investigado como opción (ver `AGENTS.md`, sección "OpenCode como operativo") pero nunca se activó para ninguna tarea real acá. |

## Fases completas sin empezar

Fase 4 (modelos predictivos), Fase 5 (capa prescriptiva) y Fase 6
(operación diaria) — ninguna tiene una sola línea de código todavía.
Detalle de qué incluye cada una, en qué orden, y qué decisiones hace
falta tomar en el camino: ver `PLAN_DE_TRABAJO.md`.
