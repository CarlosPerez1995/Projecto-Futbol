# Informe del proyecto — Fútbol (análisis deportivo)

*Última actualización: 11 nov 2026. Pensado para leerse de corrido, sin
jerga técnica innecesaria — para el detalle técnico está `AGENTS.md` y
la carpeta `docs/`. Este es el informe de **avance** (qué está hecho y
funcionando); junto a él en la raíz del repo: `INFORME_PENDIENTES.md`
(qué falta y de quién depende), `INFORME_ARQUITECTURA.md` (cómo está
diseñado) y `PLAN_DE_TRABAJO.md` (qué sigue y en qué orden).*

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

## Fase 3 — Construcción de features (26 oct 2026)

Con la base de datos lista, el siguiente paso fue convertir esos datos
crudos en las variables que un modelo predictivo puede usar. Se hizo
en tres pasos, cada uno construido sobre el anterior:

1. **Features del propio partido**: para cada partido ya jugado, cómo
   terminó — total de goles, diferencia, quién ganó (o si fue empate),
   si se pasó de determinados umbrales de goles (más de 1.5, 2.5 o 3.5
   en total), y si ambos equipos marcaron. El dato de "gol esperado"
   (xG) de Understat quedó pendiente a propósito en esta vuelta — se
   cargó después, el 11 nov, ver la sección de Fase 4 más abajo.

2. **Features de forma de cada equipo**: esta es la parte más delicada
   de toda la fase, porque acá es muy fácil cometer un error sutil que
   arruina un modelo sin que se note a simple vista — "data leakage",
   que un modelo termine entrenándose viendo, sin querer, el resultado
   que después tiene que adivinar. Para cada partido, se calculó cómo
   venía cada equipo (goles que mete y recibe en promedio, puntos,
   partidos sin recibir goles, racha actual) usando **únicamente sus
   partidos anteriores a esa fecha**, nunca el partido en cuestión.
   Esto no se dejó solo a la lógica del código: se armó un caso de
   prueba calculado a mano (tres partidos, con un resultado 0-3 bien
   llamativo) específicamente para confirmar que ese 0 y ese 3 nunca
   se filtran hacia atrás en las features de "antes del partido".

3. **Dataset final para modelar**: se juntó todo en un solo archivo,
   separando con claridad qué columnas puede usar un modelo como
   entrada (la forma de cada equipo, calculada antes del partido) y
   cuáles son la respuesta que el modelo tiene que aprender a predecir
   (el resultado real). Mezclar esas dos cosas sin esa separación
   explícita es, de nuevo, la forma más común de terminar con un
   modelo que "funciona" en las pruebas pero es inútil en la realidad.
   Cada vez que se genera este archivo queda firmado con un hash, para
   poder saber en el futuro con qué versión exacta de los datos se
   entrenó cada modelo.

Verificado contra los datos reales: 3.515 partidos, 31 columnas en
total (6 de identificación, 14 de forma de los equipos, 11 de
resultado real).

## Un pendiente que se cerró de paso (10 nov 2026)

Las cuotas de los mercados "más o menos goles" y "hándicap asiático"
(los que habían quedado fuera al cerrar fase 2) ya se cargan también —
quedó solo el mercado más simple (1x2) sin usar. Esta fue, además, la
primera tarea real que se delegó a un segundo asistente (OpenCode,
pensado para tareas rutinarias ya bien definidas, para no gastar tanto
en el asistente principal): se le dio una especificación exacta de qué
columnas usar y cómo, hizo el trabajo en su propia rama, y se verificó
a mano contra los datos reales antes de incorporarlo — cada cuota
coincide exactamente con el archivo original.

## Fase 4 — Modelos predictivos (arrancada 11 nov 2026)

Carlos autorizó instalar las 4 librerías que hacían falta
(`scikit-learn`, `scipy`, `xgboost`, `joblib`) y se arrancó. Primer
paso: dividir los partidos en tres grupos por fecha —70% para entrenar
el modelo, 15% para ajustarlo, 15% para probarlo al final— sin
mezclarlos al azar (si se mezclaran, el modelo terminaría "viendo" de
antemano partidos que después tiene que adivinar, lo mismo que ya se
había cuidado con las features de equipo en fase 3). Verificado contra
los 3.515 partidos reales: los tres grupos quedan en las proporciones
exactas y sin ningún partido compartido entre grupos.

**Segundo paso, el primer modelo de verdad**: el modelo Poisson/
Dixon-Coles, un clásico del análisis de fútbol desde los años 90. La
idea es simple de explicar aunque el cálculo detrás no lo sea: a cada
equipo se le asigna un número que representa qué tan buen ataque tiene
y otro qué tan buena defensa, usando solo los resultados reales de sus
partidos — y con esos dos números se puede calcular la probabilidad de
cualquier marcador entre dos equipos. Se entrenó un modelo separado
por cada liga y temporada (los equipos de ligas distintas nunca juegan
entre sí, no tendría sentido mezclarlos).

**La mejor prueba de que funciona**: sin decirle nada sobre la tabla de
posiciones, el modelo entrenado con los partidos de la Premier League
2024-25 le da el mejor puntaje de ataque a Liverpool (el campeón real
de esa temporada) y los tres peores puntajes a Southampton, Leicester
City e Ipswich Town — exactamente los tres equipos que de verdad
descendieron esa temporada. El modelo se mide con una métrica estándar
del área (RPS — qué tan "cerca" estuvo la predicción del resultado
real, no solo si acertó o no) contra partidos que nunca vio durante el
entrenamiento: por debajo de 0.25 en las 5 ligas, que era la meta fijada
desde el plan original. Detalle completo en
`docs/dixon_coles_resultados.md`.

**Tercer paso: un segundo modelo, con un enfoque distinto.** Mientras el
Poisson/Dixon-Coles razona "a mano" sobre goles, el segundo modelo
(XGBoost, una técnica de machine learning muy usada en la práctica)
aprende directamente a predecir quién gana a partir de las features de
forma de la Fase 3 (racha, promedio de goles, puntos recientes), sin
ningún supuesto estadístico de cómo se distribuyen los goles. Y un
cuarto paso igual de directo: el mismo enfoque pero para predecir si va
a haber más o menos de cierta cantidad de goles, y si ambos equipos van
a marcar.

**El hallazgo más importante de esta fase, y hay que decirlo con
franqueza**: al medir estos modelos contra algo mucho más simple que
cualquiera de ellos —predecir siempre lo que pasó históricamente, sin
ningún modelo— ninguno de los tres (ni el Poisson/Dixon-Coles, ni el
XGBoost de 1X2, ni el de más/menos goles y ambos marcan) le gana con
claridad y consistencia a esa comparación trivial. El código funciona
bien de punta a punta (probado, verificado a mano), pero las features
que se tenían hasta ese momento —sobre todo promedios de goles de los
últimos 5 partidos— no alcanzaban todavía para predecir mejor que "lo
de siempre".

**Carlos decidió (11 nov) probar el candidato más directo: cargar el
xG (gol esperado) real de Understat a la base de datos y agregarlo
como feature de forma del equipo (promedio de xG de los últimos 5
partidos, igual que ya se hacía con los goles), y volver a medir los
3 modelos. Resultado real, sin maquillar: el xG no cambia la
conclusión.** Comparando con la misma vara (misma calibración antes y
después, para no mezclar con un bug de calibración que se encontró y
corrigió en el camino, ver más abajo): el modelo de 1X2 mejora apenas
(0.003 en LogLoss, dentro del ruido); el de "más/menos de 2.5 goles"
mejora algo más (su AUC pasa de 0.52 a 0.56) y es el único que logra
ganarle a la comparación trivial, aunque por un margen chico; los
otros dos (más/menos de 1.5 goles, y ambos equipos marcan) no mejoran,
incluso empeoran levemente. Ninguno de los tres cruza el umbral que
pedía el plan original (AUC > 0.6). El Poisson/Dixon-Coles no usa
estas features de equipo (se calcula distinto, por liga) y no se vio
afectado.

Al volver a medir se encontró, además, un problema real en el código
de calibración de probabilidades (no relacionado con el xG): el método
que se usaba (calibración "isotónica") resultó inestable con la
cantidad de datos de validación disponible (~528 partidos) — en
algunos casos llegaba a asignarle probabilidad cero a lo que
realmente pasó, lo que arruinaba la métrica sin que el modelo en sí
hubiera empeorado. Se identificó la causa, se corrigió (se cambió a un
método más robusto para ese tamaño de muestra, "sigmoide"/Platt) y se
volvió a medir todo con la versión corregida antes de reportar estos
números — ver el detalle completo, con el paso a paso de cómo se
encontró el bug, en `docs/xgb_1x2_resultados.md` y
`docs/xgb_binary_resultados.md`.

Por esta razón, **no se sigue a la Fase 5 (la capa que decidiría
apuestas con dinero real) todavía**: hacerlo sobre modelos sin ventaja
demostrada sería irresponsable, y el candidato más directo para
resolverlo (el xG) ya se probó y no alcanzó. Queda como decisión de
Carlos cómo seguir: avanzar de todos modos sabiendo las salvedades,
buscar otra señal predictiva (ej. usar las cuotas de las casas de
apuestas, que ya están en la base de datos pero no se usan como
entrada de los modelos), o pausar esta fase.

## Dónde está el proyecto hoy (11 nov 2026)

Fases 0 a 3 completas. Fase 4 con 4 de 5 tareas hechas (split temporal,
los 3 modelos, ya re-medidos con xG) — el pipeline funciona de punta a
punta, pero ninguno de los 3 modelos muestra todavía una ventaja clara
sobre predecir la tasa histórica, ni siquiera con el xG agregado (ver
el hallazgo de arriba). La base de datos tiene, con datos reales ya
cargados: 5 ligas, 10 temporadas, 110 equipos, miles de partidos con
su marcador y su xG real, más de 130.000 filas de cuotas históricas
(los 3 mercados: 1x2, más/menos goles y hándicap asiático), la tabla
de posiciones histórica, y el dataset de features.

## Lo que sigue

Antes de nada más: con el xG ya probado y sin resolver el problema de
fondo, Carlos tiene que decidir cómo seguir (ver
`INFORME_PENDIENTES.md`). Después de eso: terminar **Fase 4** (falta
el backtesting histórico, en pausa por el mismo motivo), **Fase 5**
(la capa que decide cuánto apostar y cuándo, en pausa) y **Fase 6**
(que todo el proceso corra solo todos los días). Detalle de cada paso
y el orden exacto: `PLAN_DE_TRABAJO.md`.
