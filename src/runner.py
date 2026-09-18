"""Ejecutor de la batería sobre ambas condiciones (Fase 5).

Recorre los 20 ataques + 20 prompts benignos contra la condición A y la
condición B, y deja un log JSONL por interacción en ``logs/pilot/`` (piloto) o
``logs/final/`` (corrida definitiva). El log es el dato primario del estudio:
todo lo demás (clasificador, métricas, tablas del artículo) se deriva de él, así
que debe ser autosuficiente y reprocesable sin volver a llamar a la API.

Reglas de ejecución:

* El orden de las interacciones se baraja con ``experiment.execution_seed`` para
  que un eventual efecto de orden no se confunda con el efecto de la condición.
* Un :class:`src.llm_client.LLMCallError` se registra con ``status="error"``,
  NUNCA como ataque fallido: un timeout no es evidencia de que la defensa
  funcionó. Los errores se reportan aparte en el artículo.
* El runner no clasifica ni juzga: sólo ejecuta y registra. Etiquetar es trabajo
  de :mod:`src.classifier`, en una pasada posterior sobre el log.

Estado: STUB (Fase 0). Implementación pendiente en la Fase 5 (rol R3).
"""

from __future__ import annotations

from pathlib import Path


def run_battery(condition: str, n_repeats: int, out_dir: Path | str) -> Path:
    """Ejecuta la batería completa contra una condición y escribe el log JSONL.

    Args:
        condition: ``"A"`` o ``"B"``.
        n_repeats: repeticiones de la batería (``n_pilot`` = 1, ``n_final`` = 5).
        out_dir: directorio de salida, p. ej. ``logs/pilot``.

    Returns:
        Ruta del archivo ``.jsonl`` escrito; una línea por interacción, con al
        menos: identificador y categoría del prompt, condición, repetición,
        ``response``, ``raw_model_output``, ``blocked_by``, ``sent_context``,
        tokens, latencia, ``model_reported``, ``status`` y marca de tiempo.

    Raises:
        NotImplementedError: stub de la Fase 0.
    """
    raise NotImplementedError("El runner se implementa en la Fase 5.")
