# Auditoría de `requirements.txt` (tarea 1.5.4)

Fecha: 2026-08-06.

## Objetivo

Que `requirements.txt` refleje lo que el proyecto realmente usa, separando
dependencias de runtime de dependencias de desarrollo, y documentando por qué
existen los paquetes que no se importan en ningún `.py` del repo.

## Metodología

1. `grep -rhE "^\s*(import|from)\s+\S+" src/` sobre todos los `.py` del repo
   (fuera de `.venv/`) para listar los imports directos realmente usados.
2. `importlib.metadata.requires(...)` sobre `soccerdata`, `seleniumbase`,
   `selenium`, `wrapper-tls-requests` y `PyAutoGUI` instalados en `.venv/`
   para trazar el árbol de dependencias declaradas (no listas de `pip freeze`
   sin contexto).

## Imports directos usados en `src/futbol/`

`soccerdata`, `pandas`, `yaml` (PyYAML), `dotenv` (python-dotenv), más
stdlib (`argparse`, `logging`, `os`, `re`, `pathlib`, `datetime`,
`dataclasses`, `collections.abc`). Nada más.

## Paquetes en `requirements.txt` no importados en ningún `.py` del repo

Lista original de la tarea 1.5.4 del plan: `PyAutoGUI`, `PyGetWindow`,
`PyMsgBox`, `PyRect`, `PyScreeze`, `pytweening`, `MouseInfo`, `behave`,
`parse`, `parse_type`, `pytest-ordering`, `pytest-html`,
`pytest-rerunfailures`, `pytest-xdist`, `selenium`, `seleniumbase`,
`sbvirtualdisplay`, `python-xlib`, `python3-xlib`, `mycdp`, `pdbp`, `trio`,
`trio-websocket`, `websockets`, `wrapper-tls-requests`.

### Hipótesis verificada: todas son transitivas de `soccerdata`

`pip show soccerdata` / `importlib.metadata.requires("soccerdata")` muestra
que `soccerdata` declara como dependencias **directas y no opcionales**:
`html5lib`, `lxml`, `pandas`, `rich`, `seleniumbase`, `tqdm`, `unidecode`,
`urllib3`, `wrapper-tls-requests`.

`seleniumbase`, a su vez, declara como dependencias directas (no opcionales,
salvo los `extras` marcados con `extra ==` que no aplican aquí):
`selenium`, `PyAutoGUI`, `MouseInfo` (vía `pyautogui`), `PyGetWindow`,
`PyMsgBox`, `PyRect` (vía `pygetwindow`), `PyScreeze`, `pytweening`,
`python-xlib`/`python3-xlib`, `mycdp`, `pdbp`, `trio`, `trio-websocket`,
`websockets`, `behave`, `parse`, `parse_type`, `pytest-ordering`,
`pytest-html`, `pytest-rerunfailures`, `pytest-xdist`, `sbvirtualdisplay`.

Es decir: el 100% de los paquetes "sueltos" listados en el plan son
consecuencia de que `soccerdata` (la única fuente de datos usada hoy,
Sofascore) exige `seleniumbase` como dependencia dura — presumiblemente
porque otros lectores de `soccerdata` (FBref, WhoScored) sí usan Selenium,
aunque el lector `Sofascore` que usamos no lo necesite en tiempo de
ejecución.

## Decisión (confirmada por el usuario el 2026-08-06)

**No se remueven ni se mueven** estos paquetes de `requirements.txt`.

Motivo técnico: `pip install -r requirements.txt` (sin `--no-deps`) siempre
resuelve las dependencias declaradas por los paquetes que instala. Como
`soccerdata` exige `seleniumbase` de forma no opcional, moverlos a un
archivo `requirements-selenium.txt` no cambiaría qué se instala al correr
`pip install -r requirements.txt` — solo sería una reorganización cosmética
que podría inducir a error (parecer opcional cuando no lo es). Restructurar
la instalación para que sí sean opcionales de verdad (`requirements.txt`
mínimo + `--no-deps` + `requirements-selenium.txt` real) es un cambio de
mayor alcance que excede el estimado de 1-2 días de esta tarea y cambiaría
el comando de instalación documentado en `AGENTS.md`; se deja fuera de
1.5.4.

Si en el futuro se aprueba la tarea 1.4 de `Planes de Robustez`
(lectores FBref/WhoScored que si usan Selenium activamente), esta decisión
debería revisarse: en ese momento `seleniumbase` deja de ser "no usado
directamente" y el argumento cambia.

## Qué sí se separó en esta tarea

- **`requirements-dev.txt`** (nuevo): `pytest==9.1.1`, `pytest-cov==7.1.0`.
  `pytest` ya estaba instalado (dependencia transitiva de `seleniumbase`,
  que a su vez lo usa para su propio test runner); se declara también acá
  porque es la herramienta con la que corremos los tests del proyecto
  (tarea 1.5.5). `pytest-cov` se agrega ahora aunque recién se use en la
  tarea 6.3 (cierre de cobertura), tal como pide el plan.
- **`requirements.txt`**: sin cambios de contenido (se mantiene como estaba,
  por la decisión de arriba).

## Verificación del criterio de aceptación

Venv limpio (`python3 -m venv`) instalado desde `requirements.txt` +
`requirements-dev.txt`:

- `pip install -r requirements.txt -r requirements-dev.txt` — OK.
- `pip install -e .` — OK.
- `futbol-extract --ligas "ESP-La Liga" --temporadas 2425` — OK, genera los
  4 CSV esperados.
- `pytest tests/` — `tests/` todavía no existe (es la tarea 1.5.5, posterior
  a esta). No se puede verificar "en verde" hasta esa tarea; queda pendiente
  de confirmar cuando exista la carpeta `tests/`.
