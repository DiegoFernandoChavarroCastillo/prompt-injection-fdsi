#!/usr/bin/env python3
"""Calibra el umbral de n-gramas de L5 ejecutando SOLO prompts benignos.

L5 retiene una respuesta cuando comparte demasiados 5-gramas con las secciones
protegidas del system prompt. "Demasiados" es un número que hay que elegir, y
elegirlo mirando los ataques sería ajustar la defensa a aquello con lo que
después se la evalúa: el ASR mediría el ajuste, no la resistencia.

Así que se calibra al revés, contra los prompts benignos: se mide cuántas
coincidencias produce una respuesta legítima y se pone el umbral por encima del
máximo observado. Eso fija el FPR en cero sobre los benignos conocidos y deja la
sensibilidad en lo más estricto que la usabilidad permite.

Durante la calibración L5 está en MODO REGISTRO: calcula todas las
verificaciones pero nunca bloquea, para poder ver la distribución completa.
L3 sí actúa, porque forma parte del flujo real.

Uso:
    python scripts/calibrate_l5.py [--out notas/calibracion_L5.md]

Consume cuota: una llamada por prompt benigno (20 del conjunto de control + 15
de desarrollo = 35). No escribe en logs/: esto no son datos del experimento.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.battery import load_benign, load_dev_set  # noqa: E402
from src.chatbot_b import respond  # noqa: E402
from src.config import ConfigError, get_config  # noqa: E402
from src.defenses import l3_input_filter, l5_output_validator  # noqa: E402
from src.llm_client import LLMCallError, LLMClient  # noqa: E402


class L5EnModoRegistro:
    """L5 que analiza todo y nunca bloquea. Solo para calibrar.

    No se expone en ``try_chatbot.py``: una condición B con L5 desactivada
    parecería la condición B y no lo sería.
    """

    def __init__(self, config):
        self.config = config
        self.observaciones: list[dict] = []

    def validate_output(self, text: str) -> dict:
        evidencia = l5_output_validator.analyze(text, self.config)
        self.observaciones.append(evidencia)
        return {"passed": True, "check": None, "details": evidencia}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="notas/calibracion_L5.md")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    try:
        config = get_config()
    except ConfigError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    casos = [(b.id, b.payload, "control") for b in load_benign(config)]
    casos += [(b["id"], b["payload"], "desarrollo") for b in load_dev_set()["benign"]]

    cliente = LLMClient(config)
    filas = []
    errores = 0

    for i, (pid, payload, origen) in enumerate(casos, 1):
        registro = L5EnModoRegistro(config)
        print(f"[{i}/{len(casos)}] {pid} ({origen})", file=sys.stderr)
        try:
            resultado = respond(
                payload, client=cliente, config=config,
                l3=l3_input_filter, l5=registro,
            )
        except LLMCallError as exc:
            errores += 1
            filas.append({"id": pid, "origen": origen, "error": str(exc)[:120]})
            continue

        evidencia = registro.observaciones[0] if registro.observaciones else {}
        filas.append({
            "id": pid,
            "origen": origen,
            "payload": payload,
            "bloqueado_por_l3": resultado["blocked_by"],
            "respuesta": resultado["response"],
            "ngramas": len(evidencia.get("ngram_matches", [])),
            "ngramas_lista": evidencia.get("ngram_matches", []),
            "canary": evidencia.get("canary"),
            "delimiter": evidencia.get("delimiter"),
            "role_marker": evidencia.get("role_marker"),
            "commercial_marker": evidencia.get("commercial_marker"),
            "tokens_in": resultado["tokens_in"],
            "tokens_out": resultado["tokens_out"],
        })

    conteos = [f["ngramas"] for f in filas if "ngramas" in f]
    maximo = max(conteos) if conteos else 0
    umbral = maximo + 1

    destino = Path(args.out)
    if not destino.is_absolute():
        destino = config.project_root / destino
    destino.parent.mkdir(parents=True, exist_ok=True)

    lineas = [
        "# Calibración del umbral de n-gramas de L5",
        "",
        f"Generado por `scripts/calibrate_l5.py` el "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}.",
        f"Modelo: `{config.model}`. Prompts ejecutados: {len(casos)} "
        f"({sum(1 for f in filas if f['origen'] == 'control')} del conjunto de control, "
        f"{sum(1 for f in filas if f['origen'] == 'desarrollo')} de desarrollo).",
        f"Errores de API: {errores}.",
        "",
        "## Criterio",
        "",
        "El umbral es el **menor número de 5-gramas coincidentes que no dispara en",
        "ningún benigno**, más uno de margen. Se calibra solo con benignos: hacerlo",
        "con los ataques ajustaría la defensa a aquello con lo que se la evalúa.",
        "",
        f"- Máximo de coincidencias observado en un benigno: **{maximo}**",
        f"- Umbral fijado: **{umbral}** (`defenses.l5_ngram_threshold`)",
        "",
        "## Resultados por prompt",
        "",
        "| id | origen | n-gramas | L3 | rol | comercial | canary |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in filas:
        if "error" in f:
            lineas.append(f"| {f['id']} | {f['origen']} | — | ERROR | — | — | — |")
            continue
        lineas.append(
            f"| {f['id']} | {f['origen']} | {f['ngramas']} | "
            f"{f['bloqueado_por_l3'] or '—'} | {f['role_marker'] or '—'} | "
            f"{f['commercial_marker'] or '—'} | {f['canary']} |"
        )

    con_ngramas = [f for f in filas if f.get("ngramas")]
    if con_ngramas:
        lineas += ["", "## N-gramas concretos que coincidieron", ""]
        for f in sorted(con_ngramas, key=lambda x: -x["ngramas"]):
            lineas.append(f"**{f['id']}** ({f['ngramas']}):")
            for g in f["ngramas_lista"]:
                lineas.append(f"- `{g}`")
            lineas.append("")

    lineas += ["", "## Datos crudos", "", "```json",
               json.dumps(filas, ensure_ascii=False, indent=2), "```", ""]
    destino.write_text("\n".join(lineas), encoding="utf-8")

    print(f"\nMáximo de n-gramas en un benigno: {maximo}")
    print(f"Umbral propuesto: {umbral}")
    print(f"Errores: {errores}")
    print(f"Informe: {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
