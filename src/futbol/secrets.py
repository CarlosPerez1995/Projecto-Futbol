"""Lectura de secretos (API keys) desde variables de entorno / ``.env``.

Usa ``python-dotenv`` para cargar un archivo ``.env`` local (no
versionado, cubierto por ``.gitignore``) sin que las keys queden en
código ni en git. Ver ``.env.example`` para las variables esperadas.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def get_odds_api_key() -> str | None:
    """Devuelve ``ODDS_API_KEY`` desde el entorno (``.env`` o variable exportada).

    Returns:
        La API key, o ``None`` si no está configurada (no lanza
        excepción: el llamador decide si es obligatoria en su contexto).
    """
    return os.getenv("ODDS_API_KEY")
