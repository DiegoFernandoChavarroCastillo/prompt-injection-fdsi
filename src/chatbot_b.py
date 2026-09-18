"""Condición B — chatbot PROTEGIDO con defensa en 5 capas (Fase 4).

Orden de ejecución de las capas, de entrada a salida::

    L3 (filtro de entrada)
      -> construcción del contexto: L1 (separación de roles)
                                    L2 (instrucciones defensivas)
                                    L4 (delimitadores del input no confiable)
      -> LLM
      -> L5 (validación de salida)

Qué hace cada capa:

* **L1 — Separación de roles.** El prompt del sistema viaja en un mensaje
  ``role="system"`` propio y la entrada del usuario en un ``role="user"``
  separado. Es la diferencia estructural frente a la condición A.
* **L2 — Instrucciones defensivas.** El system prompt declara la precedencia del
  operador y prohíbe revelar el contexto o el canary.
* **L3 — Filtro de entrada.** Bloquea antes de gastar una llamada a la API;
  ver :mod:`src.defenses.l3_input_filter`.
* **L4 — Delimitadores.** La entrada del usuario se encierra en marcadores
  explícitos y se rotula como dato no confiable, no como instrucción.
* **L5 — Validación de salida.** Última red: si el canary aparece en la salida,
  la respuesta no llega al usuario; ver :mod:`src.defenses.l5_output_validator`.

Las capas deben ser genéricas, no ajustadas a la batería concreta de ataques:
un filtro escrito "a la medida" de ``attacks_v1.json`` inflaría artificialmente
la efectividad medida (ver la sección de Riesgos del plan de acción).

Estado: STUB (Fase 0). Implementación pendiente en la Fase 4 (rol R1 para
L1/L2/L4; R2 y R3 para L3 y L5). El system prompt se escribe en la Fase 1.
"""

from __future__ import annotations


def respond(user_input: str) -> dict:
    """Responde a ``user_input`` aplicando las 5 capas de defensa (condición B).

    Firma idéntica a :func:`src.chatbot_a.respond`.

    Args:
        user_input: texto del usuario (ataque o prompt benigno), sin confianza.

    Returns:
        dict con las mismas claves que la condición A:

        * ``response`` (str): texto entregado al usuario. Si L3 o L5 bloquearon,
          es el mensaje de rechazo, no la salida del modelo.
        * ``raw_model_output`` (str): salida cruda del modelo antes de L5, o
          cadena vacía si L3 bloqueó y nunca se llamó a la API.
        * ``blocked_by`` (str | None): ``"L3"``, ``"L5"`` o ``None``. Es la rama
          objetiva que el clasificador puede etiquetar sin juicio humano.
        * ``sent_context`` (str): contexto exacto enviado al modelo (system + user
          ya delimitados), para auditoría.
        * ``tokens_in`` (int | None), ``tokens_out`` (int | None): uso de la API;
          ``None`` si L3 bloqueó y no hubo llamada.
        * ``latency_ms`` (float): latencia total, incluida la de las capas.

    Raises:
        NotImplementedError: stub de la Fase 0.
        src.llm_client.LLMCallError: (una vez implementado) si la API falla tras
            los reintentos.
    """
    raise NotImplementedError("Condición B pendiente: se implementa en la Fase 4.")
