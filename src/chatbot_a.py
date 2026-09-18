"""Condición A — chatbot BASELINE VULNERABLE (Fase 3).

Esta condición existe para medir el riesgo *sin* defensas: es el punto de
comparación contra el cual se reporta la reducción de ASR de la condición B.

Diseño deliberadamente inseguro (esa es la variable independiente):
el prompt del sistema y la entrada del usuario se concatenan en UN SOLO mensaje,
con la forma::

    <contenido de prompts/system_A.txt>
    Usuario: <user_input>
    Asistente:

Al viajar todo en el mismo mensaje, el modelo no tiene forma estructural de
distinguir la instrucción legítima del operador de una instrucción inyectada por
el usuario. Esa indistinguibilidad es exactamente la vulnerabilidad OWASP LLM01
que el estudio mide. NO "arreglar" esta condición: sin ella no hay comparación.

Estado: STUB (Fase 0). Implementación pendiente en la Fase 3 (rol R1).
El system prompt que consume se escribe en la Fase 1.
"""

from __future__ import annotations


def respond(user_input: str) -> dict:
    """Responde a ``user_input`` sin ninguna defensa (condición A).

    Firma idéntica a :func:`src.chatbot_b.respond`: el runner debe poder tratar
    ambas condiciones de forma intercambiable.

    Args:
        user_input: texto del usuario, tal cual viene de la batería (ataque o
            prompt benigno). No se sanitiza: ese es el punto de la condición A.

    Returns:
        dict con las claves:

        * ``response`` (str): texto final entregado al usuario. En A es siempre
          igual a ``raw_model_output`` (no hay validación de salida).
        * ``raw_model_output`` (str): salida cruda del modelo, antes de cualquier
          post-procesamiento. Es lo que audita el clasificador.
        * ``blocked_by`` (str | None): capa que bloqueó la interacción. En A es
          siempre ``None``; la clave existe para que el log tenga el mismo
          esquema en ambas condiciones.
        * ``sent_context`` (str): texto exacto que se envió al modelo, para poder
          auditar después qué vio realmente (evidencia del Anexo B).
        * ``tokens_in`` (int | None), ``tokens_out`` (int | None): uso reportado
          por la API; base del cálculo de sobrecosto entre A y B.
        * ``latency_ms`` (float): latencia de la llamada.

    Raises:
        NotImplementedError: stub de la Fase 0.
        src.llm_client.LLMCallError: (una vez implementado) si la API falla tras
            los reintentos; el runner lo registra como error, no como ataque fallido.
    """
    raise NotImplementedError("Condición A pendiente: se implementa en la Fase 3.")
