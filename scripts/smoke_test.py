#!/usr/bin/env python3
"""Prueba de humo: una sola llamada real a la API para validar la Fase 0.

Comprueba de una vez la cadena completa: ``.env`` -> ``config/experiment.yaml``
-> :class:`src.llm_client.LLMClient` -> proveedor. Es lo primero que debe correr
cada integrante del equipo tras clonar el repositorio, y lo primero que hay que
repetir al cambiar de proveedor (Groq -> Gemini).

Imprime también ``model_reported``: el identificador EXACTO del modelo que
devuelve la API. Ese es el valor que va en la Tabla 6 del artículo, no el alias
que escribimos en el YAML.

Uso:
    python scripts/smoke_test.py

Salida: código 0 si la llamada fue exitosa; distinto de 0 en cualquier fallo
(sin API key, config inválida, error de la API), para poder encadenarlo en un
script o en CI.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Permite ejecutar el script directamente (python scripts/smoke_test.py) sin
# necesidad de instalar el paquete ni exportar PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import ConfigError, get_config  # noqa: E402
from src.llm_client import LLMCallError, LLMClient  # noqa: E402

MESSAGES = [
    {"role": "system", "content": "Responde en una frase."},
    {"role": "user", "content": "Hola, ¿qué modelo eres?"},
]


def main() -> int:
    """Ejecuta la llamada de prueba. Devuelve el código de salida del proceso."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    try:
        config = get_config()
    except ConfigError as exc:
        print(f"[ERROR] Configuración inválida: {exc}", file=sys.stderr)
        return 2

    print(f"Proveedor : {config.provider}")
    print(f"Endpoint  : {config.base_url}")
    print(f"Modelo    : {config.model} (según config)")
    print("-" * 60)

    try:
        result = LLMClient(config).chat(MESSAGES)
    except LLMCallError as exc:
        print(f"[ERROR] La llamada al modelo falló: {exc}", file=sys.stderr)
        return 1

    print(f"Texto          : {result['text']}")
    print(f"model_reported : {result['model_reported']}   <-- este va en la Tabla 6")
    print(f"tokens_in      : {result['tokens_in']}")
    print(f"tokens_out     : {result['tokens_out']}")
    print(f"latency_ms     : {result['latency_ms']:.0f}")
    print(f"finish_reason  : {result['finish_reason']}")
    print("-" * 60)
    print("OK: la Fase 0 está operativa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
