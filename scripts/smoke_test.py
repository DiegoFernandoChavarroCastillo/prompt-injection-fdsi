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

    inference = config.inference
    print(f"Proveedor : {config.provider}")
    print(f"Endpoint  : {config.base_url}")
    print(f"Modelo    : {config.model} (según config)")
    print(
        f"Inferencia: temperature={inference.temperature} top_p={inference.top_p} "
        f"max_tokens={inference.max_tokens} "
        f"reasoning_effort={inference.reasoning_effort} "
        f"include_reasoning={inference.include_reasoning}"
    )
    print("-" * 60)

    try:
        result = LLMClient(config).chat(MESSAGES)
    except LLMCallError as exc:
        print(f"[ERROR] La llamada al modelo falló: {exc}", file=sys.stderr)
        return 1

    razonamiento = result["reasoning"]
    print(f"Texto          : {result['text']}")
    print(f"model_reported : {result['model_reported']}   <-- este va en la Tabla 6")
    print(f"tokens_in      : {result['tokens_in']}")
    print(f"tokens_out     : {result['tokens_out']}")
    print(f"latency_ms     : {result['latency_ms']:.0f}")
    print(f"finish_reason  : {result['finish_reason']}")
    print(f"truncated      : {result['truncated']}")
    print(
        "reasoning      : "
        + (f"{len(razonamiento)} caracteres (fuera de 'text')" if razonamiento else "None")
    )
    print("-" * 60)

    # Comprobaciones: el smoke test debe fallar si la respuesta no es utilizable.
    problemas = []
    if not result["text"].strip():
        problemas.append("la respuesta vino vacía")
    if result["truncated"]:
        problemas.append(
            f"la respuesta quedó truncada (max_tokens={config.inference.max_tokens}); "
            "en un modelo de razonamiento el presupuesto lo consume también el razonamiento"
        )
    if razonamiento and razonamiento in result["text"]:
        problemas.append("el razonamiento se filtró dentro del texto de la respuesta")
    if problemas:
        for problema in problemas:
            print(f"[ERROR] {problema}", file=sys.stderr)
        return 1

    print("OK: la Fase 0 está operativa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
