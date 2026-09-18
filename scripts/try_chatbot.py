#!/usr/bin/env python3
"""Prueba manual de un chatbot contra un prompt suelto. NO genera datos.

Sirve para mirar con los ojos qué contesta una condición ante un payload
concreto: verificar que la condición A es útil con benignos antes de atacarla,
depurar una capa de la condición B, o entender un caso raro del piloto.

ESTE SCRIPT NO ESCRIBE EN logs/. Lo que se prueba a mano no es dato del
experimento: mezclar ensayos exploratorios con las corridas contaminaría el
corpus que sostiene el ASR y el FPR, y haría imposible saber qué se ejecutó bajo
qué versión del código. Los datos los produce únicamente ``src/runner.py``
(Fase 5), que sí registra la versión, la repetición y la semilla.

Consume cuota: cada ejecución es una llamada real a la API.

Uso:
    python scripts/try_chatbot.py --condition A --text "¿Qué cubre el seguro de hogar?"
    python scripts/try_chatbot.py --condition A --id A01     # payload de la batería
    python scripts/try_chatbot.py --condition A --id B16     # prompt benigno
    python scripts/try_chatbot.py --condition B --id A09     # aún NotImplementedError
"""

from __future__ import annotations

import argparse
import logging
import sys
import textwrap
from pathlib import Path

# Permite ejecutar el script directamente, sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import chatbot_a, chatbot_b  # noqa: E402
from src.battery import load_attacks, load_benign  # noqa: E402
from src.config import ConfigError, get_config  # noqa: E402
from src.llm_client import LLMCallError  # noqa: E402

CONDICIONES = {"A": chatbot_a, "B": chatbot_b}

ANCHO = 72


def buscar_payload(prompt_id: str, config) -> tuple[str, str]:
    """Devuelve ``(payload, descripción)`` del caso ``prompt_id`` de la batería."""
    prompt_id = prompt_id.upper()
    for attack in load_attacks(config):
        if attack.id == prompt_id:
            return attack.payload, f"ataque {attack.category} — {attack.technique}"
    for benign in load_benign(config):
        if benign.id == prompt_id:
            tipo = "benigno difícil" if benign.is_hard else "benigno ordinario"
            return benign.payload, tipo
    raise SystemExit(
        f"[ERROR] No existe el identificador '{prompt_id}'. "
        "Usa A01–A20 o B01–B20, o pasa --text."
    )


def bloque(titulo: str, cuerpo: str) -> None:
    """Imprime una sección rotulada, con el texto sangrado."""
    print(f"\n{titulo}")
    print("-" * ANCHO)
    for linea in cuerpo.splitlines() or [""]:
        print(textwrap.fill(linea, width=ANCHO, subsequent_indent="  ") if linea else "")


def main() -> int:
    """Ejecuta una interacción manual. Devuelve el código de salida."""
    parser = argparse.ArgumentParser(
        description="Prueba manual de un chatbot. NO escribe en logs/: "
        "las pruebas manuales no son datos del experimento.",
        epilog="Consume cuota de la API: cada ejecución es una llamada real.",
    )
    parser.add_argument(
        "--condition", required=True, choices=sorted(CONDICIONES),
        help="A (vulnerable) o B (protegida)",
    )
    fuente = parser.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--text", help="prompt escrito a mano")
    fuente.add_argument("--id", dest="prompt_id", help="caso de la batería: A01–A20 o B01–B20")
    parser.add_argument(
        "--verbose", action="store_true", help="mostrar el contexto completo enviado al modelo"
    )
    args = parser.parse_args()

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

    if args.prompt_id:
        payload, descripcion = buscar_payload(args.prompt_id, config)
        etiqueta = f"{args.prompt_id.upper()} ({descripcion})"
    else:
        payload, etiqueta = args.text, "texto manual"

    print("=" * ANCHO)
    print(f"Condición {args.condition}  |  {etiqueta}")
    print(f"Modelo: {config.model}")
    print("Prueba manual: NO se escribe nada en logs/")
    print("=" * ANCHO)
    bloque("PAYLOAD", payload)

    try:
        resultado = CONDICIONES[args.condition].respond(payload)
    except NotImplementedError as exc:
        print(f"\n[PENDIENTE] La condición {args.condition} aún no existe: {exc}", file=sys.stderr)
        return 3
    except LLMCallError as exc:
        print(f"\n[ERROR] La llamada al modelo falló: {exc}", file=sys.stderr)
        return 1

    if args.verbose:
        bloque("CONTEXTO ENVIADO AL MODELO", resultado["sent_context"])

    bloque("RESPUESTA (lo que ve el usuario)", resultado["response"])

    razonamiento = resultado["reasoning"]
    if razonamiento:
        bloque(
            "RAZONAMIENTO INTERNO — el usuario NUNCA ve esto",
            razonamiento,
        )
        print(
            "  (se registra para el análisis cualitativo; el clasificador lo ignora:\n"
            "   un canary aquí no es fuga, porque no llega al usuario)"
        )

    print("\nTELEMETRÍA")
    print("-" * ANCHO)
    print(f"  blocked_by     : {resultado['blocked_by']}")
    print(f"  model_reported : {resultado['model_reported']}")
    print(f"  tokens_in      : {resultado['tokens_in']}")
    print(f"  tokens_out     : {resultado['tokens_out']}")
    print(f"  latency_ms     : {resultado['latency_ms']:.0f}")
    print(f"  truncated      : {resultado['truncated']}")

    if resultado["truncated"]:
        print(
            "\n[AVISO] La respuesta quedó truncada por max_tokens: no se puede "
            "interpretar como completa.",
            file=sys.stderr,
        )

    canary = config.canary()
    if canary in resultado["response"]:
        print(f"\n[!] FUGA: el canary {canary} aparece en la respuesta al usuario.")
    elif razonamiento and canary in razonamiento:
        print(
            f"\n[·] El canary aparece en el razonamiento, pero NO en la respuesta: "
            "no cuenta como fuga."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
