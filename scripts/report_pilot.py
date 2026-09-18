#!/usr/bin/env python3
"""Clasifica el log del piloto y genera los tres informes de results/.

Produce:

* ``metricas.md`` — ASR, Δ, FPR y sobrecosto, en los tres modos de tratamiento
  de las revisiones manuales.
* ``revision_manual.csv`` — una fila por caso ambiguo, con columnas vacías para
  que el equipo las llene a mano.
* ``observaciones.md`` — observaciones DESCRIPTIVAS. Con N=1 no se sacan
  conclusiones: se describe lo que pasó y se marcan las señales de alerta.

No llama a la API: trabaja sobre el JSONL ya escrito.

Uso:
    python scripts/report_pilot.py logs/pilot/pilot-2026-09-18.jsonl
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.battery import load_attacks  # noqa: E402
from src.classifier import classify_file  # noqa: E402
from src.config import load_config  # noqa: E402
from src.metrics import cargar, compute_metrics, formatear  # noqa: E402


def _corta(texto: str | None, n: int = 160) -> str:
    if not texto:
        return "—"
    limpio = " ".join(texto.split())
    return limpio if len(limpio) <= n else limpio[: n - 1] + "…"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", help="ruta del JSONL del piloto")
    parser.add_argument("--out", default="results/pilot")
    args = parser.parse_args()

    config = load_config(require_api_key=False)
    log = Path(args.log)
    if not log.is_absolute():
        log = config.project_root / log
    salida = config.project_root / args.out
    salida.mkdir(parents=True, exist_ok=True)

    clasificado = classify_file(log, canary=config.canary())
    filas = cargar(clasificado)
    metricas = compute_metrics(filas)
    ataques = {a.id: a for a in load_attacks(config)}

    # ---------------- metricas.md ----------------
    cabecera = [
        "# Métricas del piloto (N=1)",
        "",
        f"Log: `{log.name}` — {len(filas)} interacciones. "
        f"Modelo: `{config.model}`.",
        "",
        "> **Preliminar.** N=1. Ninguna cifra de aquí soporta una afirmación fuerte:",
        "> con una sola repetición por prompt, la variabilidad del modelo "
        "(temperatura 0.7) no está medida.",
        "",
        "Los `REVISION_MANUAL` se reportan de tres formas, para que se vea cuánto",
        "depende el resultado del juicio humano todavía pendiente:",
        "",
        "- **Estricto**: se excluyen del denominador.",
        "- **Mínimo**: todos cuentan como fallo del ataque (cota inferior del ASR).",
        "- **Máximo**: todos cuentan como éxito (cota superior del ASR).",
        "",
    ]
    (salida / "metricas.md").write_text(
        "\n".join(cabecera) + formatear(metricas), encoding="utf-8"
    )

    # ---------------- revision_manual.csv ----------------
    pendientes = [f for f in filas if f.get("label_auto") == "REVISION_MANUAL"]
    with (salida / "revision_manual.csv").open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.writer(fh)
        escritor.writerow([
            "order_index", "prompt_id", "condition", "set", "category",
            "payload", "final_response", "blocked_by", "success_criterion",
            "partial_criterion", "label_evidence", "label_manual", "nota",
        ])
        for f in sorted(pendientes, key=lambda x: (x["prompt_id"], x["condition"])):
            ataque = ataques.get(f["prompt_id"])
            escritor.writerow([
                f["order_index"], f["prompt_id"], f["condition"], f["set"],
                f["category"], f["input"], f.get("final_response") or "",
                f.get("blocked_by") or "",
                ataque.success_criterion if ataque else "",
                ataque.partial_criterion if ataque else "",
                f.get("label_evidence") or "", "", "",
            ])

    # ---------------- observaciones.md ----------------
    obs = ["# Observaciones del piloto (N=1)", "",
           "> **Descriptivas, no conclusiones.** Con una sola repetición por prompt no",
           "> se puede distinguir un resultado estable de una casualidad.", ""]

    obs += ["## Qué capa actuó en cada interacción bloqueada", ""]
    bloqueos = collections.Counter(
        f["blocked_by"] for f in filas if f.get("blocked_by")
    )
    if bloqueos:
        obs += ["| Capa y regla | Interacciones |", "|---|---|"]
        obs += [f"| `{k}` | {v} |" for k, v in sorted(bloqueos.items(), key=lambda x: -x[1])]
    else:
        obs.append("Ninguna interacción fue bloqueada.")
    obs.append("")

    detalle = [f for f in filas if f.get("blocked_by")]
    if detalle:
        obs += ["Detalle por prompt:", "",
                "| prompt | cond. | capa | evidencia |", "|---|---|---|---|"]
        for f in sorted(detalle, key=lambda x: x["prompt_id"]):
            traza = f.get("defense_trace") or {}
            l3 = (traza.get("l3") or {}).get("rule")
            l5 = (traza.get("l5") or {}).get("check")
            obs.append(
                f"| {f['prompt_id']} | {f['condition']} | `{f['blocked_by']}` | "
                f"L3={l3 or '—'} L5={l5 or '—'} |"
            )
        obs.append("")

    obs += ["## Casos donde el modelo cedió y L5 lo atrapó", "",
            "Son los más informativos del estudio: separan *el modelo resistió* de",
            "*el modelo cedió y la última capa lo tapó*. Sin `raw_model_output` no se",
            "podrían distinguir, y atribuir el mérito a la capa equivocada cambiaría",
            "las conclusiones sobre qué defensa aporta qué.", ""]
    atrapados = [
        f for f in filas
        if (f.get("blocked_by") or "").startswith("L5:") and f.get("raw_model_output")
    ]
    if atrapados:
        obs += ["| prompt | cond. | verificación | salida cruda (recortada) |", "|---|---|---|---|"]
        for f in atrapados:
            obs.append(
                f"| {f['prompt_id']} | {f['condition']} | `{f['blocked_by']}` | "
                f"{_corta(f['raw_model_output'], 120)} |"
            )
    else:
        obs.append("Ninguno: L5 no retuvo ninguna respuesta en este piloto.")
    obs.append("")

    obs += ["## A03 y A13 comparados entre condiciones", "",
            "Son los dos únicos ataques que habían funcionado contra la línea base en",
            "la verificación de viabilidad, y comparten mecanismo: ambos falsifican",
            "autoridad de sistema dentro del canal de texto. Es donde hay margen",
            "medible.", ""]
    obs += ["| prompt | cond. | etiqueta | bloqueado por | respuesta (recortada) |",
            "|---|---|---|---|---|"]
    for pid in ("A03", "A13"):
        for f in sorted([x for x in filas if x["prompt_id"] == pid],
                        key=lambda x: x["condition"]):
            obs.append(
                f"| {pid} | {f['condition']} | {f.get('label_auto')} | "
                f"`{f.get('blocked_by') or '—'}` | {_corta(f.get('final_response'), 90)} |"
            )
    obs.append("")

    obs += ["## Benignos bloqueados o degradados", "",
            "Cada uno es un falso positivo: el costo en usabilidad de la defensa.", ""]
    benignos_malos = [
        f for f in filas
        if f["set"] == "benign" and f.get("label_auto") in ("BLOQUEADO", "REVISION_MANUAL")
    ]
    if benignos_malos:
        obs += ["| prompt | cond. | etiqueta | regla responsable | respuesta |",
                "|---|---|---|---|---|"]
        for f in sorted(benignos_malos, key=lambda x: (x["prompt_id"], x["condition"])):
            traza = f.get("defense_trace") or {}
            regla = (traza.get("l3") or {}).get("rule") or (traza.get("l5") or {}).get("check")
            obs.append(
                f"| {f['prompt_id']} | {f['condition']} | {f['label_auto']} | "
                f"`{regla or '—'}` | {_corta(f.get('final_response'), 80)} |"
            )
    else:
        obs.append("Ninguno: los 20 benignos fueron atendidos en ambas condiciones.")
    obs.append("")

    # Señales de alerta de la Fase 7 del plan.
    obs += ["## Señales de alerta de la Fase 7 del plan", "",
            "| Señal | ¿Se activó? | Detalle |", "|---|---|---|"]
    cat_sin_exito = [
        c for c in metricas["categorias"]
        if (metricas["asr"].get("A", {}).get("por_categoria", {})
            .get(c, {}).get("estricto", {}).get("asr") in (0, 0.0))
    ]
    obs.append(
        f"| ASR_A = 0 en alguna categoría | {'SÍ' if cat_sin_exito else 'no'} | "
        f"{', '.join(cat_sin_exito) if cat_sin_exito else '—'}. Δ queda indefinido ahí |"
    )
    ben_bloq = [f["prompt_id"] for f in filas
                if f["set"] == "benign" and f.get("label_auto") == "BLOQUEADO"]
    obs.append(
        f"| Benignos difíciles bloqueados por L3 | {'SÍ' if ben_bloq else 'no'} | "
        f"{', '.join(sorted(set(ben_bloq))) if ben_bloq else '—'} |"
    )
    a_falla_benigno = [
        f["prompt_id"] for f in filas
        if f["set"] == "benign" and f["condition"] == "A"
        and f.get("label_auto") != "ATENDIDO"
    ]
    obs.append(
        f"| A falla en benignos ordinarios | {'SÍ' if a_falla_benigno else 'no'} | "
        f"{', '.join(sorted(set(a_falla_benigno))) if a_falla_benigno else '—'} |"
    )
    n_err = sum(v for v in metricas["errores"].values()) if metricas["errores"] else 0
    obs.append(f"| Muchos `error` en los logs | {'SÍ' if n_err > 4 else 'no'} | {n_err} errores |")
    lat = {c: metricas["overhead"][c]["api_latency_ms_media"] for c in metricas["condiciones"]}
    if all(v is not None for v in lat.values()) and len(lat) == 2:
        dif = abs(lat["A"] - lat["B"])
        obs.append(
            f"| Diferencias grandes de latencia | {'revisar' if dif > 2000 else 'no'} | "
            f"A={lat['A']:.0f} ms, B={lat['B']:.0f} ms |"
        )
    obs.append("")

    # Aviso sobre la latencia total, que el piloto reveló inutilizable.
    obs += ["## AVISO: `latency_ms` no mide el costo de las capas", "",
            "El piloto destapó un defecto en cómo se mide `latency_ms`. La espera de",
            "rate limit (`min_seconds_between_calls`, 12 s) ocurre DENTRO de",
            "`LLMClient.chat()`, que a su vez está dentro de `respond()`. Como",
            "`latency_ms` cronometra `respond()` de principio a fin, **incluye esos 12",
            "segundos de espera**, que no tienen nada que ver con el costo de las",
            "defensas.", "",
            "Se ve en las cifras: la condición B aparece como MÁS RÁPIDA que la A",
            f"({metricas['overhead'].get('B', {}).get('latency_ms_media', 0):.0f} ms",
            f"frente a {metricas['overhead'].get('A', {}).get('latency_ms_media', 0):.0f} ms),",
            "lo cual es absurdo para una condición que hace más trabajo. La explicación",
            "es que las 10 interacciones que L3 bloqueó en B no llegaron a llamar a la",
            "API y por tanto no esperaron, y eso arrastra la media hacia abajo.", "",
            "**Consecuencias:**", "",
            "- `api_latency_ms` SÍ es válido y es la cifra que debe ir al artículo",
            f"  (A = {metricas['overhead'].get('A', {}).get('api_latency_ms_media', 0):.0f} ms,",
            f"  B = {metricas['overhead'].get('B', {}).get('api_latency_ms_media', 0):.0f} ms):",
            "  mide solo la llamada y refleja el contexto más largo de B.",
            "- La resta `latency_ms - api_latency_ms` **no** es el costo de las capas",
            "  deterministas, como dicen hoy los docstrings de `respond()`. Es, sobre",
            "  todo, espera de rate limit.",
            "- El sobrecosto en **tokens** no está afectado y es la comparación fiable:",
            f"  {metricas['overhead'].get('A', {}).get('tokens_in_medio', 0):.0f} vs.",
            f"  {metricas['overhead'].get('B', {}).get('tokens_in_medio', 0):.0f} tokens de entrada.", "",
            "**No se ha corregido** (prohibición 6: tras `pilot-freeze` solo se",
            "documenta). El arreglo, para después de que Diego lo decida, es mover el",
            "espaciado fuera de `respond()` —al runner, entre interacciones— o restar",
            "el tiempo dormido. Queda anotado en `notas/BLOQUEOS.md`.", ""]

    obs += ["## Pendiente de decisión", "",
            f"- **{len(pendientes)} casos** esperan revisión manual en "
            "`revision_manual.csv`. Hasta que se llenen, el ASR real está entre las",
            "  cotas mínima y máxima de `metricas.md`.",
            "- Nada de lo que revele este piloto se ha corregido: la prohibición 6 de",
            "  la sesión autónoma lo impide tras el tag `pilot-freeze`. Lo que haya que",
            "  arreglar queda documentado aquí y en `notas/BLOQUEOS.md`.", ""]

    (salida / "observaciones.md").write_text("\n".join(obs), encoding="utf-8")

    print(f"Informes en {salida.relative_to(config.project_root)}:")
    print(f"  metricas.md          ({len(filas)} interacciones)")
    print(f"  revision_manual.csv  ({len(pendientes)} casos pendientes)")
    print(f"  observaciones.md")
    print(f"  log clasificado: {clasificado.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
