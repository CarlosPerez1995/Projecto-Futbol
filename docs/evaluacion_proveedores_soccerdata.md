# Evaluación comparativa de proveedores de `soccerdata` restantes (tarea 1.4)

Investigación y documentación pura — **no se implementó ningún lector nuevo** en esta tarea. Evalúa
los proveedores de `soccerdata==1.9.1` que todavía no están en el pipeline ni planeados (todos menos
Sofascore, MatchHistory y ESPN, ya integrados/planeados en las tareas 2.1/1.2 y 1.3) contra tres
criterios: riesgo de infraestructura, información nueva real, y redundancia con lo que el propio
proyecto va a calcular en la Fase 4 del plan arquitectónico.

## Tabla de verificación técnica

Tomada tal cual de la sección 1.4 de `Frente_1_Mas_Ligas_y_Fuentes.md` (ya verificada contra el
código fuente instalado en `.venv/lib/python3.13/site-packages/soccerdata/` el 2026-08-07 — no se
volvió a derivar):

| Proveedor | Clase base | ¿Requiere Selenium/Chrome? | Métodos `read_*` disponibles | ¿En `LEAGUE_DICT` (8 ligas)? |
|---|---|---|---|---|
| Sofascore | `BaseRequestsReader` | No | `read_leagues`, `read_seasons`, `read_league_table`, `read_schedule` | Sí — ya integrado |
| MatchHistory | `BaseRequestsReader` | No | `read_games` (resultados + cuotas históricas) | Sí (5 ligas domésticas) — ya integrado (2.1) |
| ESPN | `BaseRequestsReader` | No | `read_schedule`, `read_matchsheet`, `read_lineup` | Sí — ya integrado (1.3; solo `read_schedule` en producción, ver `docs/espn_cobertura.md`) |
| **Understat** | `BaseRequestsReader` | **No** | `read_leagues`, `read_seasons`, `read_schedule`, `read_team_match_stats`, `read_player_season_stats`, `read_player_match_stats`, `read_shot_events` | Sí |
| **ClubElo** | `BaseRequestsReader` | **No** | `read_by_date`, `read_team_history` (rating ELO por equipo, sin filtrar por liga) | No aplica — no filtra por liga |
| **FBref** | `BaseSeleniumReader` | **Sí** | `read_leagues`, `read_seasons`, `read_team_season_stats`, `read_team_match_stats`, `read_player_season_stats`, `read_schedule`, `read_player_match_stats`, `read_lineup`, `read_events` | Sí |
| **WhoScored** | `BaseSeleniumReader` | **Sí** | `read_leagues`, `read_seasons`, `read_season_stages`, `read_schedule`, `read_missing_players`, `read_events` | Sí |
| **SoFIFA** | `BaseSeleniumReader` | **Sí** | `read_leagues`, `read_versions`, `read_teams`, `read_players`, `read_team_ratings`, `read_player_ratings` (ratings de videojuego, no de partidos reales) | Sí |

`FiveThirtyEight` aparece como clave de proveedor en `LEAGUE_DICT` pero **no tiene lector
implementado** en la versión instalada — no es un proveedor viable, se descarta sin evaluación
propia.

## Contexto: qué va a calcular el propio pipeline (Fase 4)

`01_Plan_de_Transformacion_Arquitectura.md` §4.2 (`Modelo Poisson / Dixon-Coles`) especifica: MLE
para **ratings de ataque/defensa por equipo** + factor rho de Dixon-Coles, calculados directamente
de los datos históricos de resultados ya integrados (Sofascore + MatchHistory), evaluados con RPS y
Brier Score. Es decir: el propio pipeline **ya va a producir su propia estimación de fuerza
ofensiva/defensiva por equipo** a partir de goles marcados/recibidos reales — sin depender de
ningún proveedor externo de ratings. Este es el criterio de redundancia contra el que se evalúan
`ClubElo`, `FBref` y `SoFIFA` más abajo, tal como pidió el usuario ("si hay información que podemos
calcular nosotros, no tiene prioridad").

Adicionalmente, `01_Plan_de_Transformacion_Arquitectura.md` §3.1 (Features por partido) ya
anticipa explícitamente "usar xG si `soccerdata` lo trae, marcar como 'pendiente fuente' si no" —
es decir, el plan arquitectónico ya esperaba necesitar una fuente de xG, sin haberla resuelto
todavía. Esto es directamente relevante para la evaluación de Understat (ver abajo).

---

## Evaluación por proveedor

### Understat

- **Riesgo:** Bajo. `BaseRequestsReader` (HTTP puro, sin Selenium/Chrome). Investigado en GitHub
  (issues #904, #905, agosto 2026): hubo roturas por bloqueo de IPs de nube/Cloudflare
  (`KeyError: 'statData'`, reportado corriendo desde Google Colab), pero se corrigieron en la
  propia v1.9.0 migrando a nuevos endpoints JSON de Understat (PR #907) — la versión fijada en este
  proyecto (`1.9.1`) ya incluye ese fix. No hay evidencia de bloqueo activo corriendo desde una IP
  residencial/no-cloud como este proyecto.
- **Información nueva real:** Alta. `read_shot_events()` da **xG a nivel de tiro individual**
  (ubicación en cancha, valor de xG por remate) — dato posicional que no se puede derivar de
  ninguna estadística agregada de partido ya disponible (Sofascore/MatchHistory/ESPN dan resultado
  y estadísticas agregadas, no eventos de tiro). Además `read_team_match_stats()` da xG/PPDA a
  nivel de partido, directamente utilizable en Fase 3.
- **Redundancia:** Ninguna — xG a nivel de tiro no es algo que el modelo Poisson/Dixon-Coles (que
  usa solo goles marcados/recibidos) vaya a producir por sí mismo. Es información complementaria,
  no un sustituto de un cálculo propio.

### ClubElo

- **Riesgo:** Bajo. `BaseRequestsReader`, sin Selenium. Investigado en GitHub: el único issue
  relevante encontrado es de mapeo de nombres de equipo/alias (PR #755, ya mergeado) — no hay
  roturas activas ni bloqueos documentados como en SoFIFA/WhoScored. Fricción operativa real:
  **no filtra por liga nativamente** (`read_by_date`/`read_team_history` devuelven todos los
  equipos con rating Elo), así que integrarlo exigiría cruzar nombres de equipo contra las ligas
  ya configuradas — trabajo de mapeo manual, no técnicamente riesgoso pero sí friccioso.
- **Información nueva real:** Media. El rating Elo de ClubElo tiene profundidad histórica mayor
  que la que este proyecto va a tener en el corto plazo (en algunos casos desde 1939, cruzando
  competiciones que este pipeline no ingesta), y se actualiza de forma continua (no por lotes como
  un reentrenamiento propio) — podría servir de prior/baseline para equipos con pocos partidos
  observados en el dataset propio (ascendidos, inicio de temporada).
- **Redundancia:** **Alta con el cálculo propio de Fase 4.2.** El objetivo de ClubElo (una
  estimación de fuerza de equipo a partir de resultados históricos) es exactamente lo que el modelo
  Poisson/Dixon-Coles va a producir con los datos ya integrados. Aplicando el criterio explícito del
  usuario ("si hay información que podemos calcular nosotros, no tiene prioridad"): **queda sin
  prioridad.** Su único valor no-redundante (mayor profundidad histórica cross-competición como
  prior de arranque) es marginal frente al costo de integrarlo — no justifica una tarea dedicada
  ahora.

### FBref

- **Riesgo:** Alto. `BaseSeleniumReader` (Chrome + `seleniumbase` requeridos). Reutilizando la
  investigación ya hecha en `01_Investigacion_Fuentes_de_Datos.md` (no re-investigado): issue
  documentado (`#880`) de que FBref dejó de scrapear `team-match-stats` para La Liga/Serie
  A/EPL/Ligue 1 pero seguía funcionando para Bundesliga — **la rotura no es uniforme ni siquiera
  dentro de la misma fuente/método**, lo que la hace particularmente difícil de detectar con un
  chequeo genérico de "0 filas" (una liga puede fallar mientras el resto del run se ve exitoso).
- **Información nueva real:** Media-Alta. A diferencia de ClubElo/SoFIFA, FBref no ofrece solo un
  rating agregado: da estadísticas granulares estilo Opta por partido/jugador (remates, pases,
  duelos, etc.) y eventos (`read_events`), que sí podrían enriquecer las features de Fase 3 más
  allá de lo que goles/resultado agregado dan. No es un sustituto directo del cálculo propio de
  ratings (que solo necesita goles), es un insumo distinto para los modelos de clasificación de
  Fase 4.3/4.4.
- **Redundancia:** Baja/parcial — no es redundante con el rating Poisson/Dixon-Coles en sí (ese
  cálculo no necesita estadísticas granulares), pero una parte de lo que aportaría (remates,
  córners, tarjetas) ya está cubierta, de forma más barata y confiable, por `MatchHistory`
  (estadísticas de partido incluidas en `read_games()`, ya integrado en 2.1). El valor incremental
  real de FBref se concentra en xG/passing granular y eventos — que Understat ya cubre para xG con
  mucho menos riesgo. Dado el costo de infraestructura (Selenium) y el patrón de rotura no uniforme
  documentado, **no se prioriza ahora**, aunque no es "redundante" en el mismo sentido que
  ClubElo/SoFIFA.

### WhoScored

- **Riesgo:** Muy alto. `BaseSeleniumReader`. Reutilizando la investigación previa (no
  re-investigada): la documentación de la propia librería **advierte explícitamente** que
  WhoScored bloquea scrapers activamente (sugiere `headless=False` "podría ayudar a evitar
  bloqueos"), y hay issues documentados de fallo de parseo de fechas (`#909`) y un bug con 3 ligas
  marcado como *wontfix* (`#715`) — es decir, ni siquiera el propio mantenedor va a arreglarlo. Es
  el proveedor con mayor riesgo de infraestructura evaluado (Selenium + bloqueo activo + bugs sin
  intención de fix).
- **Información nueva real:** Media-Alta. `read_missing_players()` (lesiones/sanciones) es un dato
  que ningún proveedor ya integrado ofrece, y sería relevante para features de Fase 3 (disponibilidad
  de plantilla). `read_events()` es similar en naturaleza a lo que ofrece FBref (eventos estilo
  Opta).
- **Redundancia:** No aplica el criterio de "lo calculamos nosotros" — la disponibilidad de
  jugadores no es algo derivable de resultados históricos. Sin embargo, el riesgo de
  infraestructura (bloqueo activo documentado por la propia librería, bugs *wontfix*) es
  desproporcionado frente al valor, más aún tratándose de un dato (lesiones) que también podría
  conseguirse de fuentes menos hostiles en el futuro.

### SoFIFA

- **Riesgo:** Muy alto — el más alto de los cinco evaluados, mayor incluso que FBref/WhoScored.
  `BaseSeleniumReader`. Investigado específicamente para esta tarea (no estaba en la investigación
  original) vía búsqueda en el repositorio de GitHub del proyecto: múltiples issues activos de
  **403 Forbidden** y **`ConnectionError`** al inicializar el scraper (issue #890, #894),
  **`IndexError: list index out of range`** en `read_teams()` (issue #413), datos faltantes para
  ligas femeninas — tabla de equipos ausente en el HTML descargado aunque la URL sea análoga a la
  masculina (issue #702). Señal más grave: existe un issue/PR específico (**#932**) para "usar
  Selenium para evitar la protección de Cloudflare" — es decir, **SoFIFA tiene protección
  anti-bot activa (Cloudflare) además del requisito base de Selenium/Chrome**, un nivel de fricción
  mayor que cualquier otro proveedor evaluado.
- **Información nueva real:** Baja para el caso de uso de este proyecto. Da ratings de jugadores y
  equipos del videojuego EA Sports FC — útil en teoría como proxy de "fuerza de plantilla",
  pero es una fuente subjetiva (juicio editorial de EA sobre el jugador), no derivada de
  desempeño en partidos reales, y se actualiza en ciclos del videojuego (no por jornada).
- **Redundancia:** **Alta con el cálculo propio de Fase 4.2**, con el mismo razonamiento que
  ClubElo: el objetivo declarado de SoFIFA (estimar la fuerza de un equipo/plantilla) es
  exactamente lo que el modelo Poisson/Dixon-Coles va a estimar empíricamente a partir de
  resultados reales — y un rating basado en resultados reales es, para el objetivo de este
  proyecto (predicción de apuestas), una señal más rigurosa que un rating editorial de videojuego.
  Aplicando el criterio explícito del usuario: **queda sin prioridad.** Combinado con el riesgo de
  infraestructura más alto de los cinco evaluados (Cloudflare + Selenium + múltiples bugs activos
  documentados), **es el candidato con peor relación riesgo/valor de toda la evaluación.**

---

## Tabla de prioridad final

| Proveedor | Prioridad | Justificación en una línea |
|---|---|---|
| **Understat** | **Alta** | Único proveedor con xG a nivel de tiro (dato no derivable de lo ya integrado), riesgo bajo (sin Selenium), y ya anticipado por el propio plan arquitectónico (Fase 3.1: "usar xG si `soccerdata` lo trae"). |
| FBref | Media | Datos granulares (passing, eventos) con valor real más allá de ratings, pero Selenium + rotura documentada no uniforme entre ligas hacen que no sea prioritario frente a Understat para el mismo tipo de dato (xG). |
| WhoScored | Baja | `read_missing_players()` es información nueva relevante (disponibilidad de plantilla), pero el riesgo de infraestructura es el más alto entre los proveedores con valor real: bloqueo activo documentado por la propia librería + bugs marcados *wontfix*. |
| ClubElo | Sin prioridad | Redundante con el rating de ataque/defensa que la Fase 4.2 va a calcular con datos propios; su único diferencial (mayor profundidad histórica cross-competición) es marginal frente al costo de integrarlo. |
| SoFIFA | Sin prioridad / Descartado | Peor relación riesgo/valor de los cinco: redundante con el cálculo propio de fuerza de equipo (y menos riguroso, al ser un rating editorial de videojuego en vez de basado en resultados reales) **+** el riesgo de infraestructura más alto (Cloudflare activo, múltiples bugs abiertos: 403/ConnectionError/IndexError). |

## Recomendación final

**Un solo candidato: Understat**, como tarea futura de integración (microplan propio, fuera del
alcance de esta tarea 1.4 — no se implementa nada acá). Es el único proveedor evaluado que combina
riesgo bajo (sin Selenium/Chrome, sin bloqueos activos conocidos en la versión fijada) con
información genuinamente nueva y no redundante (xG a nivel de tiro), y que además cierra un vacío
que el propio plan arquitectónico ya había señalado sin resolver (Fase 3.1).

**No se recomienda ningún segundo candidato en este momento.** FBref aporta valor real pero de
menor prioridad que Understat para el mismo tipo de dato (xG), a mayor riesgo de infraestructura y
mantenimiento (Selenium + rotura no uniforme documentada); WhoScored tiene el perfil de riesgo más
alto entre los proveedores no redundantes; ClubElo y SoFIFA quedan sin prioridad por ser redundantes
con el cálculo propio de la Fase 4.2, con SoFIFA además cargando el peor riesgo de infraestructura
de los cinco evaluados. Si en el futuro cambia el apetito de riesgo del proyecto (p. ej., ya se
justifica correr Selenium en producción por otra razón), FBref sería el segundo candidato a
reconsiderar — no WhoScored ni SoFIFA.

## Fuentes consultadas

- `Frente_1_Mas_Ligas_y_Fuentes.md` §1.4 (tabla de verificación técnica ya confirmada contra
  `.venv/lib/python3.13/site-packages/soccerdata/` el 2026-08-07).
- `01_Investigacion_Fuentes_de_Datos.md` (riesgo de FBref/WhoScored, reutilizado sin
  re-investigar, tal como indicaba el alcance de esta tarea).
- `01_Plan_de_Transformacion_Arquitectura.md` §3.1 y §4.2 (qué calcula el propio pipeline).
- GitHub `probberechts/soccerdata`, issues consultados el 2026-08-08 (investigación propia de esta
  tarea, no reutilizada de otro documento):
  - SoFIFA: [#413](https://github.com/probberechts/soccerdata/issues/413) (`IndexError` en
    `read_teams()`), [#890](https://github.com/probberechts/soccerdata/issues/890) (403 Forbidden),
    [#894](https://github.com/probberechts/soccerdata/issues/894) (`ConnectionError`),
    [#702](https://github.com/probberechts/soccerdata/issues/702) (datos faltantes ligas
    femeninas), [#932](https://github.com/probberechts/soccerdata/issues/932) (uso de Selenium
    para evitar protección de Cloudflare).
  - Understat: [#904](https://github.com/probberechts/soccerdata/issues/904),
    [#905](https://github.com/probberechts/soccerdata/issues/905) (bloqueo por IP de nube,
    corregido en la migración a nuevos endpoints JSON de la v1.9.0, PR #907 — ya incluida en la
    versión `1.9.1` fijada en `requirements.txt`).
  - ClubElo: [#755](https://github.com/probberechts/soccerdata/pull/755) (mapeo de nombres de
    equipo, ya mergeado).
