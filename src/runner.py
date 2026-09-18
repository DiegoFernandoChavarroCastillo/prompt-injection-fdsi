"""Ejecutor de la batería sobre ambas condiciones (Fase 5).

Recorre los prompts seleccionados contra las condiciones pedidas, N veces, y
deja un log JSONL con una línea por interacción. El log es el dato primario del
estudio: todo lo demás —clasificador, métricas, tablas del artículo— se deriva
de él, así que cada línea es autosuficiente y reprocesable sin volver a llamar a
la API.

Tres decisiones que sostienen la validez de lo que se mide:

* **Orden aleatorizado.** Todas las tuplas (condición, prompt, repetición) se
  mezclan con ``experiment.execution_seed`` antes de ejecutarse. Si A y B
  corrieran en bloques separados, cualquier deriva del proveedor a lo largo de
  la hora —latencia, carga, una actualización del modelo— quedaría confundida
  con el efecto de la condición. La semilla va en cada línea.
* **Sesión limpia por intento.** Cada interacción construye su contexto desde
  cero. No hay historial acumulado: el experimento mide inyección directa de un
  solo turno, y arrastrar turnos anteriores cambiaría el fenómeno.
* **Los errores no son fallos del ataque.** Un :class:`~src.llm_client.LLMCallError`
  se registra con ``status="error"`` y sin respuesta. Contarlo como ataque
  fallido sobrestimaría la defensa: un timeout no es evidencia de nada.

Es **reanudable**: si el archivo de salida ya existe, se saltan las tuplas que
ya tengan un resultado distinto de ``error``. Un corte a mitad de corrida no
obliga a repetir lo hecho, y reintentar los errores es volver a lanzar el mismo
comando.

Uso:
    python -m src.runner --condition both --n 1 --set all --out logs/pilot/ \\
        --run-id pilot-2026-09-18
    python -m src.runner --dry-run --n 1 --condition both --set all  # sin API
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src import chatbot_a, chatbot_b
from src.battery import load_attacks, load_benign
from src.config import Config, ConfigError, get_config
from src.llm_client import LLMCallError, LLMClient

logger = logging.getLogger(__name__)

CONDITIONS = {"A": chatbot_a, "B": chatbot_b}


@dataclass(frozen=True, slots=True)
class Tarea:
    """Una interacción a ejecutar: condición, prompt y número de repetición."""

    condition: str
    prompt_id: str
    prompt_set: str  # "attack" | "benign"
    category: str | None
    payload: str
    repetition: int

    @property
    def clave(self) -> tuple[str, str, int]:
        """Identidad de la tupla, para poder reanudar sin repetir."""
        return (self.condition, self.prompt_id, self.repetition)


class _ClienteFalso:
    """Cliente de mentira para ``--dry-run``: no toca la red ni gasta cuota."""

    def chat(self, messages: list[dict]) -> dict:
        texto = "[dry-run] Respuesta simulada; no se llamó a la API."
        return {
            "text": texto,
            "model_reported": "dry-run",
            "tokens_in": sum(len(m["content"].split()) for m in messages),
            "tokens_out": len(texto.split()),
            "latency_ms": 0.0,
            "finish_reason": "stop",
            "truncated": False,
            "reasoning": None,
        }


def git_commit_corto() -> str:
    """Hash corto del commit actual, para saber qué código produjo el log."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "desconocido"


def construir_tareas(
    config: Config, condiciones: list[str], conjunto: str, n: int
) -> list[Tarea]:
    """Arma y baraja todas las tuplas (condición, prompt, repetición).

    El barajado usa un :class:`random.Random` propio sembrado con
    ``execution_seed``, para no depender del estado global del módulo ``random``
    ni alterarlo: la reproducibilidad del orden no puede depender de si otro
    módulo pidió un número aleatorio antes.
    """
    prompts: list[tuple[str, str, str | None, str]] = []
    if conjunto in ("attacks", "all"):
        prompts += [(a.id, "attack", a.category, a.payload) for a in load_attacks(config)]
    if conjunto in ("benign", "all"):
        prompts += [(b.id, "benign", b.type, b.payload) for b in load_benign(config)]

    tareas = [
        Tarea(condition=c, prompt_id=pid, prompt_set=s, category=cat, payload=p, repetition=r)
        for c in condiciones
        for (pid, s, cat, p) in prompts
        for r in range(1, n + 1)
    ]
    random.Random(config.experiment.execution_seed).shuffle(tareas)
    return tareas


def claves_ya_hechas(destino: Path) -> set[tuple[str, str, int]]:
    """Tuplas ya registradas con un resultado utilizable (no ``error``)."""
    if not destino.exists():
        return set()
    hechas: set[tuple[str, str, int]] = set()
    for linea in destino.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            fila = json.loads(linea)
        except json.JSONDecodeError:
            logger.warning("Línea ilegible en %s; se ignora al reanudar.", destino.name)
            continue
        if fila.get("status") != "error":
            hechas.add((fila["condition"], fila["prompt_id"], fila["repetition"]))
    return hechas


def ejecutar_tarea(
    tarea: Tarea, orden: int, config: Config, client: Any, run_id: str, commit: str
) -> dict:
    """Ejecuta una interacción y devuelve la línea de log correspondiente."""
    base = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": commit,
        "execution_seed": config.experiment.execution_seed,
        "order_index": orden,
        "condition": tarea.condition,
        "prompt_id": tarea.prompt_id,
        "set": tarea.prompt_set,
        "category": tarea.category,
        "repetition": tarea.repetition,
        "model": config.model,
        "params": {
            "temperature": config.inference.temperature,
            "top_p": config.inference.top_p,
            "max_tokens": config.inference.max_tokens,
            "reasoning_effort": config.inference.reasoning_effort,
            "include_reasoning": config.inference.include_reasoning,
        },
        "input": tarea.payload,
        # Los etiqueta el clasificador en una pasada posterior, sobre una copia.
        "label_auto": None,
        "label_manual": None,
    }

    try:
        resultado = CONDITIONS[tarea.condition].respond(
            tarea.payload, client=client, config=config
        )
    except LLMCallError as exc:
        logger.error("%s %s rep%d: error de API: %s",
                     tarea.condition, tarea.prompt_id, tarea.repetition, exc)
        return {
            **base,
            "status": "error",
            "error": str(exc)[:500],
            "sent_context": None,
            "raw_model_output": None,
            "final_response": None,
            "blocked_by": None,
            "tokens_in": None,
            "tokens_out": None,
            "latency_ms": None,
            "api_latency_ms": None,
            "model_reported": None,
            "truncated": None,
            "reasoning": None,
            "defense_trace": None,
        }

    return {
        **base,
        "status": "ok",
        "error": None,
        "sent_context": resultado["sent_context"],
        "raw_model_output": resultado["raw_model_output"],
        "final_response": resultado["response"],
        "blocked_by": resultado["blocked_by"],
        "tokens_in": resultado["tokens_in"],
        "tokens_out": resultado["tokens_out"],
        "latency_ms": resultado["latency_ms"],
        "api_latency_ms": resultado["api_latency_ms"],
        "model_reported": resultado["model_reported"],
        "truncated": resultado["truncated"],
        "reasoning": resultado["reasoning"],
        "defense_trace": resultado["defense_trace"],
    }


def run_battery(
    condiciones: list[str],
    conjunto: str,
    n: int,
    destino: Path,
    run_id: str,
    config: Config | None = None,
    dry_run: bool = False,
) -> dict:
    """Ejecuta la corrida y añade una línea JSONL por interacción.

    Args:
        condiciones: ``["A"]``, ``["B"]`` o ``["A", "B"]``.
        conjunto: ``"attacks"``, ``"benign"`` o ``"all"``.
        n: repeticiones de cada prompt.
        destino: archivo ``.jsonl`` de salida (se abre en modo append).
        run_id: identificador de la corrida, presente en cada línea.
        config: configuración a usar.
        dry_run: si es ``True``, no se llama a la API.

    Returns:
        Resumen con ``total``, ``ejecutadas``, ``saltadas``, ``errores``.
    """
    config = config or get_config()
    tareas = construir_tareas(config, condiciones, conjunto, n)
    hechas = claves_ya_hechas(destino)
    commit = git_commit_corto()
    # Un solo cliente para toda la corrida: reconstruirlo en cada interacción
    # reiniciaría su espaciado de rate limit y dispararía los 429.
    client = _ClienteFalso() if dry_run else LLMClient(config)

    destino.parent.mkdir(parents=True, exist_ok=True)
    ejecutadas = saltadas = errores = 0

    with destino.open("a", encoding="utf-8") as salida:
        for orden, tarea in enumerate(tareas):
            if tarea.clave in hechas:
                saltadas += 1
                continue
            fila = ejecutar_tarea(tarea, orden, config, client, run_id, commit)
            salida.write(json.dumps(fila, ensure_ascii=False) + "\n")
            salida.flush()  # un corte no debe perder lo ya ejecutado
            ejecutadas += 1
            if fila["status"] == "error":
                errores += 1
            logger.info(
                "[%d/%d] %s %s rep%d -> %s",
                ejecutadas + saltadas, len(tareas), tarea.condition,
                tarea.prompt_id, tarea.repetition,
                fila["blocked_by"] or fila["status"],
            )

    return {
        "total": len(tareas),
        "ejecutadas": ejecutadas,
        "saltadas": saltadas,
        "errores": errores,
        "destino": str(destino),
    }


def main(argv: Iterable[str] | None = None) -> int:
    """Punto de entrada de línea de comandos."""
    parser = argparse.ArgumentParser(description="Ejecuta la batería y registra el log.")
    parser.add_argument("--condition", choices=["A", "B", "both"], default="both")
    parser.add_argument("--n", type=int, default=1, help="repeticiones por prompt")
    parser.add_argument("--set", dest="conjunto", choices=["attacks", "benign", "all"],
                        default="all")
    parser.add_argument("--out", default="logs/pilot/", help="directorio o archivo .jsonl")
    parser.add_argument("--run-id", default=None, help="identificador de la corrida")
    parser.add_argument("--dry-run", action="store_true",
                        help="no llamar a la API; usa un cliente falso")
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    try:
        config = get_config() if not args.dry_run else _config_sin_clave()
    except ConfigError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    run_id = args.run_id or ("dry-run" if args.dry_run else
                             datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ"))
    destino = Path(args.out)
    if not destino.is_absolute():
        destino = config.project_root / destino
    if destino.is_dir() or args.out.endswith("/"):
        destino = destino / f"{run_id}.jsonl"

    condiciones = ["A", "B"] if args.condition == "both" else [args.condition]
    resumen = run_battery(
        condiciones, args.conjunto, args.n, destino, run_id, config, args.dry_run,
    )

    print(f"\nCorrida '{run_id}' terminada.")
    print(f"  tuplas totales : {resumen['total']}")
    print(f"  ejecutadas     : {resumen['ejecutadas']}")
    print(f"  saltadas       : {resumen['saltadas']} (ya estaban en el log)")
    print(f"  errores        : {resumen['errores']}")
    print(f"  log            : {resumen['destino']}")
    if resumen["errores"]:
        print("\n  Vuelve a lanzar el mismo comando para reintentar solo los errores.")
    return 0


def _config_sin_clave() -> Config:
    """Configuración para ``--dry-run``: no hace falta API key si no hay API."""
    from src.config import load_config

    return load_config(require_api_key=False)


if __name__ == "__main__":
    raise SystemExit(main())
