#!/usr/bin/env python3
"""Congela la batería: escribe data/MANIFEST.txt con los hashes SHA-256.

Esto es el **preregistro** del instrumento de medición. La validez del ASR
depende de que los 20 ataques se hayan escrito sin conocer el comportamiento de
las defensas: si se retocaran después de ver qué bloquea L3, el ASR mediría lo
bien que se ajustó la batería al filtro, no lo bien que el filtro resiste.

El manifiesto deja constancia verificable de cuándo se fijó el contenido.
``tests/test_battery.py`` falla si los JSON cambian sin regenerarlo, de modo que
cualquier modificación posterior es un acto explícito y visible en el historial,
no un ajuste silencioso. La contraparte en git es el tag ``battery-v1``.

Uso:
    python scripts/freeze_battery.py            # congela, o confirma que no hay cambios
    python scripts/freeze_battery.py --force    # re-congela tras un cambio deliberado

Sin ``--force``, si el contenido cambió respecto al manifiesto existente, el
script se niega a sobrescribirlo y devuelve código 1: regenerar el manifiesto
debe ser una decisión consciente y documentada del equipo, no un efecto
colateral de volver a correr un script.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Permite ejecutar el script directamente, sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.battery import load_attacks, load_benign, parse_manifest, sha256_of  # noqa: E402
from src.config import Config, ConfigError, load_config  # noqa: E402

NOTA = "Batería congelada antes de implementar L3/L5."

CABECERA = """\
# Manifiesto de congelación de la batería (preregistro) — proyecto FDSI
#
# {nota}
#
# Los hashes de abajo fijan el contenido exacto de los 20 ataques y los 20
# prompts benignos en el momento en que se escribieron, antes de que existiera
# ninguna defensa contra la que ajustarlos. Si el ASR se midiera con una batería
# retocada a posteriori, mediría el ajuste de los ataques al filtro y no la
# resistencia del filtro a los ataques.
#
# tests/test_battery.py compara estos hashes con el contenido actual y falla si
# difieren. Regenerar este archivo (scripts/freeze_battery.py --force) es un acto
# deliberado que debe quedar documentado en el artículo.
#
# Generado por scripts/freeze_battery.py — no editar a mano.
"""


def construir_manifiesto(config: Config) -> str:
    """Arma el texto del manifiesto a partir del contenido actual de los JSON."""
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    attacks, benign = load_attacks(config), load_benign(config)
    raiz = config.project_root

    lineas = [
        CABECERA.format(nota=NOTA),
        f"frozen_at_utc: {ahora}",
        f"note: {NOTA}",
        "",
        f"attacks_file: {config.paths.attacks.relative_to(raiz)}",
        f"attacks_sha256: {sha256_of(config.paths.attacks)}",
        f"attacks_entries: {len(attacks)}",
        f"attacks_bytes: {config.paths.attacks.stat().st_size}",
        "",
        f"benign_file: {config.paths.benign.relative_to(raiz)}",
        f"benign_sha256: {sha256_of(config.paths.benign)}",
        f"benign_entries: {len(benign)}",
        f"benign_bytes: {config.paths.benign.stat().st_size}",
        "",
    ]
    return "\n".join(lineas)


def main() -> int:
    """Escribe o verifica el manifiesto. Devuelve el código de salida."""
    parser = argparse.ArgumentParser(description="Congela la batería de prueba.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-congelar aunque el contenido haya cambiado (decisión deliberada)",
    )
    args = parser.parse_args()

    try:
        config = load_config(require_api_key=False)
        nuevo = construir_manifiesto(config)
    except ConfigError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    destino = config.paths.manifest
    nuevos = parse_manifest(nuevo)

    if destino.exists():
        previos = parse_manifest(destino.read_text(encoding="utf-8"))
        cambios = [
            clave
            for clave in ("attacks_sha256", "benign_sha256")
            if previos.get(clave) != nuevos[clave]
        ]
        if not cambios:
            print(f"Sin cambios: la batería sigue coincidiendo con {destino.name}.")
            print(f"  congelada el : {previos.get('frozen_at_utc', '?')}")
            print(f"  attacks      : {previos.get('attacks_sha256', '?')}")
            print(f"  benign       : {previos.get('benign_sha256', '?')}")
            return 0
        if not args.force:
            print(
                f"[ERROR] La batería cambió respecto a {destino.name}: {', '.join(cambios)}.",
                file=sys.stderr,
            )
            for clave in cambios:
                print(f"  {clave}", file=sys.stderr)
                print(f"    manifiesto : {previos.get(clave, '(ausente)')}", file=sys.stderr)
                print(f"    actual     : {nuevos[clave]}", file=sys.stderr)
            print(
                "\nSi el cambio es deliberado, documéntalo en el artículo y vuelve a "
                "correr con --force. Si no lo es, revierte los archivos de data/.",
                file=sys.stderr,
            )
            return 1
        print(f"[AVISO] Re-congelando tras un cambio deliberado: {', '.join(cambios)}")

    destino.write_text(nuevo, encoding="utf-8")
    print(f"Manifiesto escrito en {destino.relative_to(config.project_root)}")
    print(f"  frozen_at_utc  : {nuevos['frozen_at_utc']}")
    print(f"  attacks_sha256 : {nuevos['attacks_sha256']}  ({nuevos['attacks_entries']} entradas)")
    print(f"  benign_sha256  : {nuevos['benign_sha256']}  ({nuevos['benign_entries']} entradas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
