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


def validate_output(text: str) -> dict:
    """Decide si la salida del modelo puede entregarse al usuario.

    Args:
        text: texto crudo devuelto por el modelo, sin modificar.

    Returns:
        dict con las claves:

        * ``passed`` (bool): ``True`` si la salida puede entregarse. Ojo con la
          polaridad: es la inversa de ``blocked`` en
          :func:`src.defenses.l3_input_filter.check_input`. Aquí ``True`` es el
          caso bueno.
        * ``check`` (str | None): identificador corto y estable de la
          verificación que falló (p. ej. ``"canary_en_salida"``,
          ``"delimitador_en_salida"``, ``"ngramas_system_prompt"``), o ``None``
          si pasó. Acaba en ``blocked_by`` como ``"L5:<verificación>"``. Nunca
          se muestra al usuario: el mensaje de rechazo es idéntico al de L3.
        * ``details`` (dict): evidencia de la verificación —el n-grama que
          coincidió, la posición del canary, el umbral aplicado—, para poder
          auditar la decisión en el Anexo B sin repetir la llamada.

    El texto de reemplazo NO se decide aquí: cuando ``passed`` es ``False``,
    :mod:`src.chatbot_b` entrega ``prompts/messages.yaml::l5_fallback``, que es
    idéntico al de L3 para que el usuario no pueda distinguir qué capa actuó.

    Raises:
        NotImplementedError: stub. Se implementa en la Fase 4c.
    """
    raise NotImplementedError(
        "L5 pendiente: validate_output() se implementa en la Fase 4c."
    )
