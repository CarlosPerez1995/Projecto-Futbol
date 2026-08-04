# AGENTS.md

## Resumen del proyecto
Proyecto personal de predicción de apuestas de fútbol usando la librería `soccerdata`.
Flujo: Extracción -> Transformación/normalización -> Modelo de datos en BD ->
Modelos estadísticos/predictivos/prescriptivos -> Recomendaciones de apuestas.

Estado actual: **etapa inicial (solo extracción de datos)**.

## Entorno técnico
- Python 3.x, entorno virtual en `.venv/`
- SO: Debian 13
- Base de datos planeada: SQLite (vía `sqlite3`, incluido en la stdlib)

## Dependencias principales
- `soccerdata` (fuente: https://github.com/probberechts/soccerdata)
- `pandas`
- `openpyxl` (necesario para exportar a `.xlsx`)

## Reglas estrictas para el agente (anti-alucinación)

1. NUNCA inventes métodos, parámetros o clases de `soccerdata` (u otra librería)
   que no hayas verificado. Si no estás seguro de que algo existe, inspecciona
   el paquete instalado en `.venv/lib/python*/site-packages/soccerdata/` o dilo
   explícitamente en vez de asumirlo.
2. Antes de usar un método nuevo de una librería externa, confírmalo revisando
   el código fuente instalado o pidiendo confirmación al usuario.
3. No agregues dependencias nuevas al proyecto sin preguntar primero.
4. Usa siempre rutas compatibles con Linux (`pathlib.Path`), nunca rutas de
   Windows tipo `C:\...`.
5. Sigue PEP8. Usa type hints donde aporte claridad.
6. Cambios de código mínimos y quirúrgicos: no reescribas archivos completos
   si solo se pidió modificar una función o sección.
7. Si una tarea es ambigua, pregunta antes de asumir.
8. Sé conciso en las respuestas salvo que se pida una explicación detallada.
9. Evita crear múltiples instancias de `Sofascore()` si se puede reutilizar
   una sola instancia — cada instanciación puede implicar llamadas a la API.
10. Todo script que escriba archivos debe crear las carpetas de salida si no
    existen (`Path(...).mkdir(parents=True, exist_ok=True)`).

## Flujo de extracción de datos
1. Instanciar `soccerdata.Sofascore()` una sola vez por sesión/liga.
2. Extraer ligas con `read_leagues()`
3. Extraer temporadas con `read_seasons()`
4. Extraer tablas de posiciones con `read_league_table()`
5. Extraer calendarios de partidos con `read_schedule()`

## Notas importantes
- Fuente de datos: Sofascore
- Todas las columnas de fecha requieren manejo de zona horaria
  (`pd.to_datetime(..., errors="coerce").dt.tz_localize(None)`)
- Archivos Excel se usan como almacenamiento intermedio (por ahora)
- Integración con base de datos: planeada, no implementada aún

## Estructura del proyecto
- `HistoryData.py` — script principal de extracción de datos (en refactor)
- `data/` — carpeta de salida para archivos Excel/CSV generados
- `.venv/` — entorno virtual (no versionar en git)
- `requirements.txt` — dependencias del proyecto
- Scripts de procesamiento de datos — por crear
- Esquema de base de datos — por definir

## Comandos útiles
- Activar entorno: `source .venv/bin/activate`
- Instalar dependencias: `pip install -r requirements.txt`
- Ejecutar script principal: `python3 HistoryData.py`
- Congelar dependencias tras instalar: `pip freeze > requirements.txt`
