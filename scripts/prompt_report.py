#!/usr/bin/env python3
"""Informe de los system prompts: tamaño aproximado y diff A vs. B.

Genera la evidencia de simetría entre condiciones que se adjunta al Anexo B: el
diff unificado muestra que la condición B es la A más los bloques de defensa,
sin un solo cambio en la identidad, el dominio ni las políticas.

El conteo de tokens es una **estimación** (palabras x 1.4), suficiente para
dimensionar el sobrecosto fijo del system prompt antes de gastar llamadas. Las
cifras que van al artículo son las de ``tokens_in`` que reporta la API en cada
interacción, no estas.

Uso:
    python scripts/prompt_report.py            # informe completo
    python scripts/prompt_report.py --no-diff  # solo los tamaños

No llama a la API y no consume cuota.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

# Permite ejecutar el script directamente, sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import ConfigError, load_config  # noqa: E402
from src.prompts import (  # noqa: E402
    PROTECTED_SECTIONS,
    extract_sections,
    load_prompts,
    section_names,
)

#: Factor palabra -> token. Aproximación gruesa para español; el español gasta
#: más tokens por palabra que el inglés por acentos y morfología.
TOKENS_POR_PALABRA = 1.4


def tokens_aprox(texto: str) -> int:
    """Estima los tokens de ``texto`` como palabras x 1.4, redondeado."""
    return round(len(texto.split()) * TOKENS_POR_PALABRA)


def fila(nombre: str, texto: str) -> str:
    """Formatea una línea de la tabla de tamaños."""
    return (
        f"{nombre:<34} {len(texto):>7} {len(texto.split()):>9} {tokens_aprox(texto):>9}"
    )


def main() -> int:
    """Imprime el informe. Devuelve el código de salida del proceso."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-diff", action="store_true", help="omitir el diff entre system_A y system_B"
    )
    args = parser.parse_args()

    try:
        config = load_config(require_api_key=False)
        prompts = load_prompts(config)
    except ConfigError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    protegido = extract_sections(prompts.system_B, PROTECTED_SECTIONS)

    print("=" * 72)
    print("TAMAÑO DE LOS PROMPTS (tokens estimados = palabras x 1.4)")
    print("=" * 72)
    print(f"{'artefacto':<34} {'chars':>7} {'palabras':>9} {'tokens~':>9}")
    print("-" * 72)
    print(fila("system_A.txt  (condición A)", prompts.system_A))
    print(fila("system_B.txt  (condición B)", prompts.system_B))
    print(fila("l2_reminder.txt  (L2, por turno)", prompts.l2_reminder))
    print(fila("mensaje de rechazo L3", prompts.l3_rejection))
    print(fila("mensaje de rechazo L5", prompts.l5_fallback))
    print("-" * 72)
    print(fila("secciones protegidas (cotejo L5)", protegido))
    print("-" * 72)

    delta_tokens = tokens_aprox(prompts.system_B) - tokens_aprox(prompts.system_A)
    por_turno = delta_tokens + tokens_aprox(prompts.l2_reminder)
    base = tokens_aprox(prompts.system_A)
    print(f"Sobrecosto fijo de B en el system prompt : +{delta_tokens} tokens~")
    print(f"Sobrecosto total por turno (system + L2) : +{por_turno} tokens~", end="")
    print(f"  ({por_turno / base:.0%} sobre A)" if base else "")
    print()
    print(f"Secciones en A: {section_names(prompts.system_A)}")
    print(f"Secciones en B: {section_names(prompts.system_B)}")
    print(f"Cotejadas por L5: {PROTECTED_SECTIONS}")
    print()

    prefijo = prompts.system_B.startswith(prompts.system_A)
    print(f"¿system_B empieza exactamente con system_A?  {'SÍ' if prefijo else 'NO'}")
    if not prefijo:
        print(
            "  ATENCIÓN: se rompió la simetría experimental. La diferencia de ASR "
            "entre A y B ya no sería atribuible solo a las capas de defensa.",
            file=sys.stderr,
        )

    if not args.no_diff:
        print()
        print("=" * 72)
        print("DIFF UNIFICADO system_A.txt -> system_B.txt")
        print("=" * 72)
        diff = difflib.unified_diff(
            prompts.system_A.splitlines(keepends=True),
            prompts.system_B.splitlines(keepends=True),
            fromfile="prompts/system_A.txt",
            tofile="prompts/system_B.txt",
            n=1,
        )
        sys.stdout.writelines(diff)

    return 0 if prefijo else 1


if __name__ == "__main__":
    raise SystemExit(main())
