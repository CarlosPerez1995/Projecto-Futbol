# Pendientes del proyecto — Fútbol

*Última actualización: 11 nov 2026. Complementa a `INFORME_PROYECTO.md`
(qué está hecho) — acá va solo lo que falta y de quién depende.*

## Pendiente activo — sin dueño concreto todavía

**Fase 5 está pausada (decisión de Carlos, 11 nov) mientras se busca
una estrategia con una señal genuinamente independiente del
mercado** — el backtest real (`docs/backtest_resultados.md`) mostró
que apostar según "EV positivo" contra las cuotas de mercado pierde
85% del banco simulado en 1X2 y 49% en over/under 2.5; ni la forma
histórica (Fase 3) ni el xG (primera ronda del 11 nov) alcanzaron por
sí solos, y las cuotas de mercado, aunque mejoraron las métricas
predictivas, no sirven para apostar contra ese mismo mercado (detalle
matemático de por qué en el mismo doc).

**No hay todavía un candidato concreto elegido** para esa señal
independiente — ejemplos de qué podría explorarse, sin que ninguno
esté decidido ni empezado: alineaciones probables/lesiones (dato no
extraído hoy — `get_espn_lineup` existe en el código pero está roto
contra la API actual de ESPN, ver `docs/espn_cobertura.md`, habría que
arreglarlo o buscar otra fuente), un modelo de xG propio en vez de
depender del de Understat, o aceptar usar los modelos solo como
referencia informativa sin automatizar apuestas de dinero real. Queda
para cuando Carlos (o quien delegue) decida por dónde seguir.

**Fase 5 sigue en pausa** hasta entonces — ver `PLAN_DE_TRABAJO.md`.

## Resueltos recientemente

- **Decisión de Carlos sobre Fase 5 (11 nov)**: pausar mientras se
  busca una señal independiente del mercado — ver pendiente activo
  arriba.
- **Backtesting real de EV/Kelly (11 nov)**: decisión de Carlos
  ejecutada (avanzar a Fase 5) y backtesteada contra cuotas reales
  antes de construir nada más — resultado real: pérdida severa, ver
  pendiente activo arriba y `docs/backtest_resultados.md`.
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

## Estado de las fases que faltan

Fase 4 (modelos predictivos) ya tiene sus 5 tareas hechas, incluido el
backtesting. Fase 5 (capa prescriptiva) tiene 1 de 3 tareas hechas
(EV/Kelly + backtest) y está en pausa por el hallazgo de arriba — las
otras 2 (recomendaciones diarias, registro de apuestas) no se
construyeron a propósito. Fase 6 (operación diaria) no tiene una sola
línea de código todavía, depende de que Fase 5 se resuelva. Detalle de
qué incluye cada una, en qué orden, y qué decisiones hace falta tomar
en el camino: ver `PLAN_DE_TRABAJO.md`.
