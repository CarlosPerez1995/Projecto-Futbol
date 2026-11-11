"""Modelo Poisson / Dixon-Coles (tarea 4.2, Fase 4).

Modelo estadístico clásico para resultados de fútbol (Maher 1982,
extendido por Dixon & Coles 1997): cada equipo tiene un parámetro de
ataque y uno de defensa; los goles de local y de visitante se modelan
como Poisson independientes cuyas medias dependen de esos parámetros
más una ventaja de local — y Dixon-Coles agrega una corrección
(``rho``) porque el Poisson independiente puro subestima los empates y
los marcadores muy bajos (0-0, 1-0, 0-1, 1-1).

Fórmulas (verificadas contra Dixon & Coles 1997, no inventadas):

    λ (goles esperados del local)    = exp(ataque_local + defensa_visitante + ventaja_local)
    μ (goles esperados del visitante) = exp(ataque_visitante + defensa_local)
    P(x,y) = τ(x,y; λ,μ,ρ) · Poisson(x; λ) · Poisson(y; μ)

    τ(0,0) = 1 − λμρ
    τ(0,1) = 1 + λρ
    τ(1,0) = 1 + μρ
    τ(1,1) = 1 − ρ
    τ(x,y) = 1 para cualquier otro marcador

Un equipo con defensa débil (deja marcar mucho) tiene un parámetro de
defensa ALTO: ``defensa_i`` aparece en la fórmula de goles esperados
del RIVAL cuando juega contra ``i``, no en los propios — es la
convención estándar del modelo, no una elección arbitraria.

Alcance de esta implementación, reducido a propósito:
- Un modelo por ``(league_code, season_code)``, ajustado solo con los
  partidos de esa liga/temporada en el split de entrenamiento — los
  equipos de distintas ligas nunca juegan entre sí en este dataset, no
  tiene sentido compartir parámetros entre ligas.
- Sin ponderación por recencia (Dixon-Coles original pesa partidos más
  recientes más fuerte con un decaimiento exponencial) — se deja para
  una iteración futura si hace falta, no se pierde de vista.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

logger = logging.getLogger(__name__)

MAX_GOALS_GRID = 10  # suficiente cola para integrar P(H)/P(D)/P(A) de la conjunta
_TAU_FLOOR = 1e-10  # salvaguarda numérica: evita log(0) o log(negativo) por rho extremo

# Rangos razonables para la optimización (ver literatura de Dixon-Coles:
# ataque/defensa normalmente entre -2 y 2 en escala log; rho normalmente
# pequeño, entre -0.2 y 0.2) — no son límites arbitrarios, evitan que el
# optimizador divergiera a soluciones degeneradas con equipos de pocos datos.
BOUNDS_ATTACK_DEFENSE = (-3.0, 3.0)
BOUNDS_HOME_ADVANTAGE = (-1.0, 1.0)
BOUNDS_RHO = (-0.2, 0.2)


def _tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    """Corrección de Dixon-Coles para marcadores bajos."""
    if x == 0 and y == 0:
        return 1 - lam * mu * rho
    if x == 0 and y == 1:
        return 1 + lam * rho
    if x == 1 and y == 0:
        return 1 + mu * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def _dixon_coles_prob(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    tau = max(_tau(x, y, lam, mu, rho), _TAU_FLOOR)
    return tau * poisson.pmf(x, lam) * poisson.pmf(y, mu)


@dataclass
class DixonColesModel:
    """Modelo ajustado para una liga/temporada. No reentrenar a mano los
    campos — usar ``fit_dixon_coles``.
    """
    teams: list[str]
    team_index: dict[str, int]
    attack: np.ndarray
    defense: np.ndarray
    home_advantage: float
    rho: float

    def lambda_mu(self, home_team: str, away_team: str) -> tuple[float, float]:
        i = self.team_index[home_team]
        j = self.team_index[away_team]
        lam = float(np.exp(self.attack[i] + self.defense[j] + self.home_advantage))
        mu = float(np.exp(self.attack[j] + self.defense[i]))
        return lam, mu

    def match_outcome_probs(self, home_team: str, away_team: str) -> tuple[float, float, float]:
        """Probabilidades ``(P(H), P(D), P(A))`` integrando la conjunta
        de marcadores hasta ``MAX_GOALS_GRID`` goles por lado, y
        renormalizando para que sumen exactamente 1 (el truncado de la
        cola infinita y el propio ``tau`` dejan una suma ligeramente
        distinta de 1, se corrige acá, no antes).
        """
        lam, mu = self.lambda_mu(home_team, away_team)
        p_h = p_d = p_a = 0.0
        for x in range(MAX_GOALS_GRID + 1):
            for y in range(MAX_GOALS_GRID + 1):
                p = _dixon_coles_prob(x, y, lam, mu, self.rho)
                if x > y:
                    p_h += p
                elif x == y:
                    p_d += p
                else:
                    p_a += p
        total = p_h + p_d + p_a
        return p_h / total, p_d / total, p_a / total


def fit_dixon_coles(
    matches: pd.DataFrame,
    home_col: str = "home_team",
    away_col: str = "away_team",
    home_score_col: str = "home_score",
    away_score_col: str = "away_score",
) -> DixonColesModel:
    """Ajusta un ``DixonColesModel`` por máxima verosimilitud sobre
    ``matches`` (todos del mismo liga/temporada — no se filtra acá,
    responsabilidad del caller, ver ``fit_and_evaluate_by_group``).
    """
    teams = sorted(set(matches[home_col]) | set(matches[away_col]))
    team_index = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    home_idx = matches[home_col].map(team_index).to_numpy()
    away_idx = matches[away_col].map(team_index).to_numpy()
    home_goals = matches[home_score_col].to_numpy()
    away_goals = matches[away_score_col].to_numpy()

    # Máscaras de los 4 casos especiales de tau, precalculadas una sola vez
    # (no cambian entre llamadas del optimizador, solo rho cambia).
    mask_00 = (home_goals == 0) & (away_goals == 0)
    mask_01 = (home_goals == 0) & (away_goals == 1)
    mask_10 = (home_goals == 1) & (away_goals == 0)
    mask_11 = (home_goals == 1) & (away_goals == 1)

    def neg_log_likelihood(params: np.ndarray) -> float:
        """Vectorizada sobre todos los partidos a la vez (sin loop en
        Python): un loop por partido acá, multiplicado por las
        decenas/cientos de evaluaciones que hace L-BFGS-B hasta
        converger, tardaba minutos por liga/temporada — medido
        corriendo contra los datos reales (ver AGENTS.md)."""
        alpha = params[:n]
        beta = params[n:2 * n]
        gamma = params[2 * n]
        rho = params[2 * n + 1]
        lam = np.exp(alpha[home_idx] + beta[away_idx] + gamma)
        mu = np.exp(alpha[away_idx] + beta[home_idx])

        tau = np.ones_like(lam)
        tau[mask_00] = 1 - lam[mask_00] * mu[mask_00] * rho
        tau[mask_01] = 1 + lam[mask_01] * rho
        tau[mask_10] = 1 + mu[mask_10] * rho
        tau[mask_11] = 1 - rho
        tau = np.maximum(tau, _TAU_FLOOR)

        ll = np.sum(np.log(tau) + poisson.logpmf(home_goals, lam) + poisson.logpmf(away_goals, mu))
        return -ll

    x0 = np.concatenate([np.zeros(n), np.zeros(n), [np.log(1.3)], [0.0]])
    bounds = [BOUNDS_ATTACK_DEFENSE] * (2 * n) + [BOUNDS_HOME_ADVANTAGE, BOUNDS_RHO]

    resultado = minimize(neg_log_likelihood, x0, method="L-BFGS-B", bounds=bounds)
    if not resultado.success:
        logger.warning("fit_dixon_coles: el optimizador no convergió del todo: %s", resultado.message)

    alpha = resultado.x[:n]
    beta = resultado.x[n:2 * n]
    # Gauge: el modelo es invariante a alpha_i += c, beta_i -= c para
    # todo i (ver docstring del módulo) — se fija la ambigüedad
    # centrando el ataque en 0, que es la convención estándar de la
    # literatura, no un ajuste post-hoc que cambie las predicciones.
    centro = alpha.mean()
    alpha = alpha - centro
    beta = beta + centro

    return DixonColesModel(
        teams=teams,
        team_index=team_index,
        attack=alpha,
        defense=beta,
        home_advantage=float(resultado.x[2 * n]),
        rho=float(resultado.x[2 * n + 1]),
    )


def rps(probs: tuple[float, float, float], outcome: str) -> float:
    """Ranked Probability Score para 3 resultados ordenados (H, D, A).

    ``probs`` = ``(p_h, p_d, p_a)``. Penaliza más una predicción
    equivocada "lejos" (ej. predecir victoria local fuerte y que gane
    el visitante) que una equivocación "cerca" (predecir empate y que
    gane cualquiera) — por eso el orden H/D/A importa, no es una lista
    arbitraria de 3 categorías sin relación entre sí (para eso está
    ``brier_score``).
    """
    o = {"H": (1, 0, 0), "D": (0, 1, 0), "A": (0, 0, 1)}[outcome]
    cum_p = cum_o = total = 0.0
    for i in range(2):  # r-1 = 2 términos para r=3 resultados
        cum_p += probs[i]
        cum_o += o[i]
        total += (cum_p - cum_o) ** 2
    return total / 2


def brier_score(probs: tuple[float, float, float], outcome: str) -> float:
    """Brier Score multiclase estándar (sin asumir orden entre categorías)."""
    o = {"H": (1, 0, 0), "D": (0, 1, 0), "A": (0, 0, 1)}[outcome]
    return sum((p - oi) ** 2 for p, oi in zip(probs, o))


def fit_and_evaluate_by_group(
    train_df: pd.DataFrame,
    eval_df: pd.DataFrame,
) -> pd.DataFrame:
    """Ajusta un ``DixonColesModel`` por cada ``(league_code,
    season_code)`` presente en ``train_df`` y lo evalúa (RPS, Brier)
    contra las filas correspondientes de ``eval_df``.

    Si un grupo no tiene ninguna fila en ``eval_df`` (ej. una temporada
    ya completa que cae entera en entrenamiento, sin partidos futuros
    para probar — pasa de verdad con los datos reales de este
    proyecto, ver `INFORME_PROYECTO.md`), sus métricas quedan en
    ``NaN`` — no se inventa un número.
    """
    filas = []
    for (liga, temporada), grupo_train in train_df.groupby(["league_code", "season_code"]):
        modelo = fit_dixon_coles(grupo_train)
        grupo_eval = eval_df[
            (eval_df["league_code"] == liga) & (eval_df["season_code"] == temporada)
        ]

        if len(grupo_eval) == 0:
            filas.append({
                "league_code": liga, "season_code": temporada,
                "n_train": len(grupo_train), "n_eval": 0,
                "rps": float("nan"), "brier": float("nan"),
            })
            continue

        rps_vals, brier_vals = [], []
        for _, row in grupo_eval.iterrows():
            if row["home_team"] not in modelo.team_index or row["away_team"] not in modelo.team_index:
                logger.warning(
                    "fit_and_evaluate_by_group: %s/%s %s-%s tiene un equipo no visto en "
                    "entrenamiento, se omite esa fila",
                    liga, temporada, row["home_team"], row["away_team"],
                )
                continue
            probs = modelo.match_outcome_probs(row["home_team"], row["away_team"])
            rps_vals.append(rps(probs, row["result_1x2"]))
            brier_vals.append(brier_score(probs, row["result_1x2"]))

        filas.append({
            "league_code": liga, "season_code": temporada,
            "n_train": len(grupo_train), "n_eval": len(rps_vals),
            "rps": sum(rps_vals) / len(rps_vals) if rps_vals else float("nan"),
            "brier": sum(brier_vals) / len(brier_vals) if brier_vals else float("nan"),
        })

    return pd.DataFrame(filas)
