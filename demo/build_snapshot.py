#!/usr/bin/env python3
"""Congela en ``demo/data/snapshot.json`` lo que la demo necesita del log final.

La demo tiene que funcionar sin internet y en la máquina de cualquier integrante,
pero ``logs/final/*.jsonl`` no se versiona (ver ``.gitignore``). Este script
extrae del log clasificado solo dos cosas, y el resultado sí se versiona:

* las cinco repeticiones A y B de cada prompt predefinido, que son la respuesta
  de respaldo cuando la API no está disponible;
* las métricas de :func:`src.metrics.compute_metrics`, para el panel de
  resultados.

No llama a la API. Se vuelve a ejecutar si cambia el log (por ejemplo, cuando
se incorporen las etiquetas de la revisión manual).

Uso:
    python demo/build_snapshot.py
    python demo/build_snapshot.py logs/final/final-2026-10-20_classified.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.presets import PRESET_IDS  # noqa: E402
from src.config import PROJECT_ROOT, load_config  # noqa: E402
from src.metrics import compute_metrics, cargar  # noqa: E402

DEFAULT_LOG = PROJECT_ROOT / "logs" / "final" / "final-2026-10-20_classified.jsonl"
SNAPSHOT = PROJECT_ROOT / "demo" / "data" / "snapshot.json"

#: Campos de cada interacción que la interfaz usa. El razonamiento interno se
#: deja fuera a propósito: el usuario nunca lo ve, tampoco en la demo.
CAMPOS = (
    "order_index", "condition", "prompt_id", "repetition", "final_response",
    "raw_model_output", "blocked_by", "sent_context", "tokens_in", "tokens_out",
    "latency_ms", "api_latency_ms", "defense_trace",
)

#: Orden de preferencia para elegir la repetición que se reproduce por defecto.
#: Se prefiere la que mejor enseña el caso; el recuento de las cinco va al lado,
#: así que elegir la más vistosa no oculta nada.
PREFERENCIA = ("EXITO_TOTAL", "REVISION_MANUAL", "ATENDIDO", "FALLO", "BLOQUEADO", "DEGRADADO")


def _etiqueta(fila: dict) -> str:
    return fila.get("label_manual") or fila["label_auto"]


def construir(log: Path) -> dict:
    filas = cargar(log)
    config = load_config(require_api_key=False)
    canary = config.canary()

    grabadas: dict[str, dict] = {}
    for pid in PRESET_IDS:
        grabadas[pid] = {}
        for cond in ("A", "B"):
            reps = sorted(
                (f for f in filas if f["prompt_id"] == pid and f["condition"] == cond),
                key=lambda f: f["repetition"],
            )
            if not reps:
                raise SystemExit(f"{pid}/{cond} no está en {log}")
            elegida = min(reps, key=lambda f: PREFERENCIA.index(_etiqueta(f)))
            interaccion = {c: elegida.get(c) for c in CAMPOS}
            interaccion["label"] = _etiqueta(elegida)
            grabadas[pid][cond] = {
                "interaction": interaccion,
                "labels": dict(Counter(_etiqueta(f) for f in reps)),
                "n": len(reps),
            }

    texto = json.dumps(grabadas, ensure_ascii=False)
    if canary in texto:
        # El canary viaja dentro de sent_context (es parte de system_B). Se
        # enmascara aquí para que el snapshot versionado no lo contenga.
        grabadas = json.loads(texto.replace(canary, "⟦CANARY⟧"))

    # Tokens medios por conversación sobre TODAS las interacciones: las que L3
    # cortó cuentan como 0, porque no se pagaron. Es la base del costo efectivo
    # (compute_metrics promedia solo las que llamaron al modelo).
    efectivos = {}
    for cond in ("A", "B"):
        de_cond = [f for f in filas if f["condition"] == cond]
        efectivos[cond] = {
            "tokens_in": sum(f["tokens_in"] or 0 for f in de_cond) / len(de_cond),
            "tokens_out": sum(f["tokens_out"] or 0 for f in de_cond) / len(de_cond),
            "model_calls": sum(1 for f in de_cond if f["tokens_in"]),
            "n": len(de_cond),
        }

    return {
        "source_log": log.name,
        "run_id": filas[0]["run_id"],
        "git_commit": filas[0]["git_commit"],
        "model": filas[0]["model"],
        "metrics": compute_metrics(filas),
        "effective_tokens": efectivos,
        "recorded": grabadas,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("log", nargs="?", default=str(DEFAULT_LOG))
    args = parser.parse_args()

    snapshot = construir(Path(args.log))
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Escrito {SNAPSHOT.relative_to(PROJECT_ROOT)} "
          f"({len(snapshot['recorded'])} prompts, run {snapshot['run_id']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
