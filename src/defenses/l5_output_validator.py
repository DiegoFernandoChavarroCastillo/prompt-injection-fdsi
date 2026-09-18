"""L5 — Validación de salida (Fase 4).

Última red de la condición B: revisa lo que el modelo produjo antes de
entregárselo al usuario. Su caso central es el canary
(``prompts/canary.txt``): si el token centinela del system prompt aparece en la
salida, hubo fuga de contexto y la respuesta no debe entregarse.

L5 importa porque es la única capa que actúa cuando las anteriores ya fallaron:
la inyección funcionó y el modelo está a punto de revelar el contexto. Su
detección del canary es objetiva (coincidencia de cadena) y por eso el
clasificador puede etiquetar esta rama sin auditoría manual.

Estado: STUB (Fase 0). Implementación pendiente en la Fase 4 (rol R3).
"""

from __future__ import annotations


def validate(model_output: str) -> dict:
    """Decide si la salida del modelo puede entregarse al usuario.

    Args:
        model_output: texto crudo devuelto por el modelo, sin modificar.

    Returns:
        dict con las claves:

        * ``blocked`` (bool): ``True`` si la salida se retiene.
        * ``reason`` (str | None): identificador corto y estable del motivo
          (p. ej. ``"canary_en_salida"``), o ``None`` si pasó.
        * ``safe_output`` (str): texto a entregar al usuario: la salida original
          si pasó, o el mensaje de rechazo si se bloqueó. Nunca debe contener el
          canary ni fragmentos del system prompt.

    Raises:
        NotImplementedError: stub de la Fase 0.
    """
    raise NotImplementedError("L5 pendiente: se implementa en la Fase 4.")
