# Tareas programadas (17 nov 2026)

Decisión de Carlos: identificar tareas repetitivas del proyecto y
automatizarlas, para no gastar tiempo del jefe de proyecto en
ejecutarlas a mano. Ambas son secuencias deterministas (no necesitan
un agente LLM, ni OpenCode ni Claude Code) — `systemd --user timer`,
mismo patrón ya usado en otro frente del hub (Punky Soluciones).

## Qué corre y cuándo

- **`futbol-refresh-data.timer`** → `scripts/refresh_data.py`, todos
  los lunes 06:00. Extrae datos nuevos (`futbol-extract`), los carga a
  la BD (loaders idempotentes, no se borra nada), corre
  `validate_data.py` y reconstruye `model_dataset.csv`. Si la
  validación encuentra errores nuevos, el servicio termina con código
  de error (visible en `systemctl --user status` / `journalctl`) —
  no se auto-corrige nada, queda para que lo revise el jefe de
  proyecto.
- **`futbol-coverage.timer`** → `scripts/measure_coverage.py`, el 1°
  de cada mes 07:00. Corre `pytest --cov=futbol` y guarda un reporte
  en `data/reports/coverage_<fecha>.{json,txt}` con qué archivos
  quedan bajo el 40% que pide el plan (tarea 6.3). Nunca termina con
  error (bajar cobertura es información, no un dato roto) — excepto si
  la suite de tests en sí falla.

## Por qué NO usan OpenCode

Ambas tareas son mecánicas y deterministas — no hace falta un agente
para "decidir" nada. Usar un LLM (OpenCode, con `bash: allow` ya
habilitado desde el 17 nov) para ejecutar una secuencia fija de
comandos sería gastar tokens en algo que un script ya resuelve gratis
y de forma más confiable. **OpenCode queda reservado para el trabajo
de seguimiento que sí requiere criterio**: si `measure_coverage.py`
señala un módulo con cobertura baja, el jefe de proyecto revisa cuáles
líneas faltan y, si corresponde, delega a OpenCode escribir esos tests
puntuales (tarea única, revisada antes de mergear — mismo patrón ya
usado el 10 nov) — no se le pide que decida solo qué testear.

## Instalación (ya hecha en esta máquina, 17 nov 2026)

```bash
mkdir -p ~/.config/systemd/user
ln -sf <repo>/scripts/systemd/futbol-refresh-data.service ~/.config/systemd/user/
ln -sf <repo>/scripts/systemd/futbol-refresh-data.timer   ~/.config/systemd/user/
ln -sf <repo>/scripts/systemd/futbol-coverage.service     ~/.config/systemd/user/
ln -sf <repo>/scripts/systemd/futbol-coverage.timer       ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now futbol-refresh-data.timer futbol-coverage.timer
```

`loginctl show-user <usuario> -p Linger` debe decir `Linger=yes` para
que los timers corran sin sesión gráfica/login activa — ya estaba
habilitado en esta máquina (por el mismo patrón de Punky Soluciones).

## Verificar / deshacer

```bash
systemctl --user list-timers | grep futbol        # próxima corrida
journalctl --user -u futbol-refresh-data.service   # logs de la última corrida
journalctl --user -u futbol-coverage.service

systemctl --user disable --now futbol-refresh-data.timer futbol-coverage.timer  # deshacer
```
