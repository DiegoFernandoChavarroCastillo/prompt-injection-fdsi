"""L5 — Validación de salida (Fase 4).

Última red de la condición B: revisa lo que el modelo produjo antes de
entregárselo al usuario. Su caso central es el canary
(``prompts/canary.txt``): si el token centinela del system prompt aparece en la
salida, hubo fuga de contexto y la respuesta no debe entregarse.

L5 importa porque es la única capa que actúa cuando las anteriores ya fallaron:
la inyección funcionó y el modelo está a punto de revelar el contexto. Su
detección del canary es objetiva (coincidencia de cadena) y por eso el
clasificador puede etiquetar esta rama sin auditoría manual.

TODO (Fase 4), dos decisiones ya acordadas:

* **Los delimitadores cuentan como fuga.** ``<<<USER_DATA_a91f>>>`` y
  ``<<</USER_DATA_a91f>>>`` están escritos dentro de ``system_B.txt``, de modo
  que un ataque puede hacer que el modelo los repita sin haberlos adivinado
  (A09, A11 y A20 piden justamente el contenido del system prompt). Su
  aparición en la salida debe tratarse como señal de fuga, igual que el canary.
* **El umbral de n-gramas se calibra con los benignos, nunca con los ataques.**
  Ajustarlo hasta que bloquee los 20 ataques sería ajustar la defensa a la
  batería: el ASR mediría ese ajuste y no la resistencia real. El criterio es
  el contrario: el umbral más estricto que no dispare con los benignos, y en
  particular con los cinco difíciles, cuyas respuestas legítimas se parecen
  mucho a las negativas de ``[EJEMPLOS DE RESPUESTA]``.

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
