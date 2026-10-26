# Informe del proyecto — Fútbol (análisis deportivo)

*Última actualización: 26 oct 2026. Pensado para leerse de corrido, sin
jerga técnica innecesaria — para el detalle técnico está `AGENTS.md` y
la carpeta `docs/`.*

## De qué se trata

La idea es construir, paso a paso, un sistema que extraiga datos reales
de fútbol (resultados, calendarios, estadísticas, cuotas de apuestas),
los guarde ordenados en una base de datos, y con eso termine generando
recomendaciones de apuestas con una lógica de negocio seria (valor
esperado, gestión de banca) — no una corazonada. El plan siempre fue en
fases: primero conseguir los datos de forma confiable, después
organizarlos en una base de datos, después construir features y
modelos predictivos, después la capa de decisión, y al final dejarlo
corriendo solo todos los días.

Hoy (26 oct 2026) las dos primeras fases están completas y se está
arrancando la tercera.

## Fase 0 — Poner la casa en orden (3-6 ago 2026)

Antes de escribir nada nuevo, había que limpiar lo que ya existía: un
único script (`HistoryData.py`) sin versionar bien, sin `.gitignore`,
sin una convención clara de ramas. Se resolvió eso: el repo quedó
ordenado, con `requirements.txt` completo y una rama de desarrollo
(`desarrollo`) separada de la rama estable (`main`).

## Fase 1 — Extracción de datos (4-8 ago 2026)

Esta fase terminó siendo mucho más grande que lo planeado originalmente.
La idea inicial era extraer de una sola fuente (Sofascore: calendarios,
resultados, tabla de posiciones). En la práctica se sumaron tres fuentes
más, porque cada una aporta algo que las otras no tienen:

- **Sofascore** — calendario, resultados, tabla de posiciones.
- **MatchHistory** (football-data.co.uk) — resultados históricos *y*
  cuotas de apuestas de más de 20 casas distintas.
- **ESPN** — calendario (de respaldo/cruce).
- **Understat** — estadísticas avanzadas (xG, el "gol esperado" que
  usan los analistas para medir qué tan buenas fueron las ocasiones de
  un equipo, más allá del resultado).

También se dejó una base técnica sólida para que todo lo que viniera
después no se construyera sobre arena: el código se reorganizó como un
paquete instalable, los valores por defecto (qué ligas, qué
temporadas) se movieron a un archivo de configuración en vez de estar
escondidos en el código, se armó un lugar seguro para claves de API
futuras, y se empezaron a escribir pruebas automáticas (`pytest`) desde
el principio en vez de dejarlas para el final — una lección de
disciplina que se mantuvo en las fases siguientes.

**Nota sobre una confusión que hubo en el camino:** a comienzos de
octubre circuló un reporte que decía que el proyecto solo tenía las
fases 0 y 1 "a medias". Ese reporte estaba mal — toda la fase 1, con
las 4 fuentes integradas, ya estaba cerrada desde el 8 de agosto, dos
meses antes. Se corrigió la documentación cuando se detectó el error.

## La pausa (ago-oct 2026)

Entre el 8 de agosto y mediados de octubre el proyecto quedó en pausa
mientras Carlos priorizaba otros frentes (el plan de caja de Punky
Soluciones). No se tocó nada en ese período — ni para bien ni para mal.

## Fase 2 — Modelo de datos (13-14 oct 2026)

Esta es la fase donde pasó la mayoría de las decisiones interesantes.
El objetivo: tomar todos los archivos CSV sueltos de la fase 1 y
organizarlos en una base de datos real (SQLite), con tablas que se
relacionen entre sí correctamente.

### El problema que no estaba en ningún plan: los equipos no se llaman igual en todas las fuentes

Al diseñar las tablas apareció un problema real que ningún documento de
planificación había anticipado (porque se escribieron antes de sumar
las fuentes nuevas): **las 4 fuentes no se refieren al mismo equipo con
el mismo nombre ni con el mismo número de identificación**. Un ejemplo
real: el Wolverhampton aparece como "Wolverhampton" en Sofascore,
"Wolverhampton Wanderers" en ESPN y Understat, y "Wolves" en
MatchHistory — tres formas distintas de nombrar al mismo equipo, sin
ningún código compartido entre fuentes.

La solución fue armar a mano una tabla de equivalencias para los 110
equipos de las 5 ligas que se extraen por defecto (23+23+21+20+23), y
verificarla automáticamente contra los datos reales para asegurarse de
que no quedó ningún equipo sin mapear ni ninguna confusión entre dos
equipos parecidos (por ejemplo, Manchester United y Manchester City).
Se decidió **no** usar un algoritmo de coincidencia "aproximada" para
esto — con nombres de equipo cortos y parecidos entre sí, un algoritmo
así puede confundir dos equipos distintos sin que nadie lo note, y eso
es peor que no resolverlo del todo.

### El bug del huso horario

Al intentar reconocer que un mismo partido real venía reportado por las
4 fuentes a la vez, apareció otro hallazgo: **MatchHistory reporta la
hora del partido en hora local de Reino Unido, mientras que las otras
3 fuentes ya vienen en hora UTC**. En horario de verano británico eso
es una hora de diferencia (un partido que las demás fuentes marcan a
las 19:00, MatchHistory lo marca a las 20:00); en horario de invierno
no hay diferencia porque en esa época UTC y hora de Reino Unido
coinciden. Antes de corregir esto, casi un tercio de los partidos (31%)
no se reconocían como "el mismo partido" entre fuentes. Después de
ajustar la comparación para que tolere hasta 6 horas de diferencia (en
vez de exigir la hora exacta), ese número bajó a 0,65% — y los pocos
casos que quedan sin cruzar están identificados y documentados, no
escondidos.

### Qué se sobrescribe y qué queda como historial — decisión de Carlos

Una decisión importante que tomó Carlos sobre cómo tratar los datos que
cambian con el tiempo:

- **Resultados de partidos** (marcador, si ya se jugó o no): se
  sobrescriben siempre con el dato más reciente. Tiene sentido — el
  resultado de un partido no "cambia" con el tiempo, solo se corrige si
  hubo un error.
- **Cuotas de apuestas** y **tabla de posiciones**: acá Carlos pidió lo
  contrario — **guardar el historial completo**, sin sobrescribir nada.
  La razón es de cara al futuro: un modelo predictivo puede sacarle
  mucho más jugo a saber *cómo se movió* una cuota en los días previos
  al partido, o en qué posición estaba un equipo *antes* de cada
  partido, que a solo conocer el último valor. Guardar el historial
  ahora evita tener que rehacer todo este trabajo más adelante cuando
  se necesite ese dato.

Esto obligó a cambiar el diseño de la base de datos dos veces después
de la primera versión (siempre agregando una versión nueva del
esquema, nunca editando la anterior, para no perder el rastro de cómo
fue evolucionando).

### Un par de bugs reales encontrados y corregidos antes de llegar a producción

- Al revisar el diseño antes de usarlo con datos reales, se encontró
  que la forma en que se evitaban cuotas duplicadas tenía un hueco: la
  base de datos (SQLite) trata cada valor "vacío" como distinto de
  cualquier otro valor vacío, así que en un caso particular (el mercado
  de apuestas 1x2, que no usa el campo de "línea" de hándicap) la
  protección contra duplicados no funcionaba. Se corrigió antes de que
  llegara a tener datos reales cargados.
- Al cargar miles de filas de una sola vez, el sistema tardaba varios
  minutos porque guardaba cada fila por separado en el disco. Se
  corrigió para guardar en bloques, y la misma carga pasó de varios
  minutos a unos pocos segundos.

### Cómo se verificó que todo esto funciona de verdad

Más allá de las pruebas automáticas (64 en total, todas en verde), se
corrió el proceso completo contra los datos reales extraídos en fase 1
y se revisaron los resultados a mano. El resultado más satisfactorio:
la tabla de posiciones calculada por el sistema coincide, equipo por
equipo y punto por punto, con la tabla real de la Premier League
2024-25 (Liverpool campeón con 84 puntos, Arsenal segundo con 74,
Manchester City tercero con 71). No es una coincidencia menor — es la
prueba de que todo el trabajo de identificar equipos, cruzar partidos
entre fuentes y calcular posiciones está bien hecho.

También se generó un reporte de calidad de datos (un Excel con
resumen y lista de errores) que no encontró ningún problema: cero
partidos duplicados, cero fechas fuera de rango, cero marcadores
negativos, cero referencias rotas entre tablas.

### Qué quedó fuera de esta fase, a propósito

De las cuotas de apuestas solo se cargó el mercado más simple (1x2:
quién gana, quién pierde o si es empate). MatchHistory también trae
mercados de "más o menos goles" y de hándicap, pero con un formato de
columnas que cambia de temporada a temporada — se decidió dejarlos para
una iteración futura en vez de arriesgar un diseño apresurado. Está
documentado, no se perdió de vista.

## Dónde está el proyecto hoy (26 oct 2026)

Fase 2 completa. La base de datos tiene, con datos reales ya cargados:
5 ligas, 10 temporadas, 110 equipos, miles de partidos con su marcador,
decenas de miles de filas de cuotas históricas, y la tabla de
posiciones histórica. Carlos acaba de autorizar arrancar la **Fase 3:
construcción de features** — el paso que convierte estos datos crudos
en las variables que un modelo predictivo puede usar (por ejemplo,
cuántos goles promedia un equipo en sus últimos 5 partidos, su racha
actual, si juega de local o visitante).

## Lo que viene después de fase 3

Según el plan original: Fase 4 (modelos predictivos — estadísticos y de
machine learning), Fase 5 (la capa que decide cuánto apostar y cuándo,
con gestión de riesgo), y Fase 6 (que todo el proceso corra solo todos
los días, sin intervención manual).
