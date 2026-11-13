# Notas de `config/team_aliases.json` (tarea 2.3, resolución de equipos)

Documenta cómo se armó el mapeo de nombres de equipo entre fuentes que
usa `resolve_team()` de `src/futbol/db/load_data.py`, para que quede
claro que es trabajo verificado contra datos reales, no inventado
(regla 1 de AGENTS.md).

## Por qué hace falta un mapeo manual

`db/schema_v1.sql` ya documenta el hallazgo: Sofascore, ESPN, Understat
y MatchHistory (football-data.co.uk) no comparten ningún id de equipo,
y tampoco el mismo nombre exacto. Verificado extrayendo el set completo
de nombres de equipo de las 5 ligas configuradas por defecto
(`config/config.yaml`) desde los 4 CSV reales de la corrida del 8 ago
2026 (`data/raw/{sofascore,espn,understat,match_history}/`):

| Liga | Equipos | Ejemplo de divergencia |
| --- | --- | --- |
| ENG-Premier League | 23 | "Wolverhampton" (sofascore) / "Wolverhampton Wanderers" (espn, understat) / "Wolves" (match_history) |
| ESP-La Liga | 23 | "Athletic Club" (sofascore, espn, understat) / "Ath Bilbao" (match_history) |
| FRA-Ligue 1 | 21 | "Olympique Lyonnais" (sofascore) / "Lyon" (espn, understat, match_history) |
| GER-Bundesliga | 20 | "1. FC Köln" (sofascore) / "FC Cologne" (espn, understat) / "FC Koln" (match_history) |
| ITA-Serie A | 23 | "Inter" (sofascore, understat, match_history) / "Internazionale" (espn) |

Ninguna regla mecánica simple (sacar tildes, sacar sufijos como "FC")
cubre todos los casos — `Wolves` y `Ath Bilbao` son apodos/abreviaturas,
no transformaciones de texto del nombre largo. Por eso el mapeo es una
tabla curada a mano, no un algoritmo de fuzzy matching: con nombres de
equipo cortos y parecidos entre sí (ej. "Manchester United" vs.
"Manchester City"), un fuzzy match por similitud de texto arriesga
falsos positivos que son peores que no resolver el equipo (corrompen
en silencio el dataset predictivo más adelante).

## Cómo se armó y verificó

1. Se extrajo, por liga, el set completo de nombres únicos de equipo
   (columnas `home_team`/`away_team`, o `team` en `standings`) de cada
   una de las 4 fuentes.
2. Como las 4 fuentes tienen la misma cantidad de equipos por liga
   (23/23/21/20/23), es un problema de **coincidencia uno a uno**
   dentro de cada liga, no de clasificación difusa: se resolvió cada
   equipo por inspección manual de los 5 sets en paralelo (nombre
   oficial, historia del club, abreviaturas conocidas del fútbol
   europeo).
3. Se verificó mecánicamente el resultado contra los CSV reales
   (script ad hoc, no versionado): para cada liga y cada fuente, el set
   de nombres que aparece en `team_aliases.json` es **exactamente
   igual** (ni de más ni de menos) al set real extraído de los CSV, y
   no hay dos equipos canónicos distintos mapeando al mismo nombre de
   una fuente (colisión). Las 5 ligas × 4 fuentes (20 combinaciones)
   pasaron sin diferencias.

## Qué pasa con un equipo que no está en el archivo

`resolve_team()` lanza `ValueError` explícito (no adivina). Esto va a
pasar la primera vez que se cargue una temporada con ascensos/descensos
no vistos todavía (ej. 2526 trae equipos distintos a 2425 en algunas
ligas) — hay que agregar esa fila a mano a `team_aliases.json` antes de
poder cargar esa corrida, igual que ya se hizo para 2425.

## Qué queda pendiente

- Esto solo cubre las 5 ligas de `config/config.yaml` y la temporada
  2425 extraída hasta ahora. La temporada 2526 (y cualquier liga nueva)
  va a traer equipos sin mapear todavía — normal, no es un bug.
- El id nativo de equipo (`source_team_id` en `team_source_ids`) solo
  se completa para Understat (es la única de las 4 fuentes que trae un
  id de equipo propio en los datasets ya integrados); para las demás
  queda `NULL`, resuelto solo por nombre.
