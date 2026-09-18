"""Condición B — chatbot PROTEGIDO con defensa en 5 capas (Fase 4).

Orden de ejecución de las capas, de entrada a salida (ver PlanDeAccion.md,
Fase 4)::

    entrada
      -> L3 (filtro de entrada)  -> [bloqueo -> mensaje neutro]
      -> contexto: system_B (incluye L4) + L1 (roles y delimitadores)
                   + L2 (recordatorio posterior)
      -> LLM
      -> L5 (validación de salida)  -> [falla -> fallback]
      -> respuesta

Qué hace cada capa:

* **L1 — Delimitación estructural.** ``system_B`` viaja en un mensaje
  ``role="system"`` propio y la entrada del cliente en un ``role="user"``,
  envuelta en ``<<<USER_DATA_a91f>>> … <<</USER_DATA_a91f>>>``. Si la entrada
  trae el propio delimitador hay que escaparlo antes de envolverla, o el
  atacante podría cerrar el bloque de datos. La declaración de que ese bloque
  es dato y no instrucción está en la sección ``[SEGURIDAD — ENTRADA DEL
  USUARIO]`` de ``prompts/system_B.txt``.
* **L2 — Sándwich.** ``prompts/l2_reminder.txt`` se reinyecta DESPUÉS del bloque
  delimitado, para que la última instrucción del contexto sea del operador y no
  del atacante. Documentar si va dentro del mismo mensaje ``user`` o como
  mensaje aparte.
* **L3 — Filtro de entrada.** Bloquea antes de gastar una llamada a la API;
  ver :mod:`src.defenses.l3_input_filter`.
* **L4 — Anti-leaking.** Ya está en ``prompts/system_B.txt`` (Fase 1): las
  secciones ``[SEGURIDAD — CONFIDENCIALIDAD]`` y ``[EJEMPLOS DE RESPUESTA]``.
  Aquí solo hay que verificar que se esté enviando.
* **L5 — Validación de salida.** Última red: canary, solapamiento de 5-gramas
  contra :data:`src.prompts.PROTECTED_SECTIONS` y marcadores de rol o de
  compromiso comercial; ver :mod:`src.defenses.l5_output_validator`.

TODO (Fase 4): los delimitadores ``<<<USER_DATA_a91f>>>`` y
``<<</USER_DATA_a91f>>>`` están escritos dentro de ``system_B.txt``, así que un
ataque puede extraerlos sin adivinarlos. L5 debe tratar su aparición en la
salida como señal de fuga, igual que el canary. Y el umbral de n-gramas se
calibra con los benignos, nunca con los ataques: calibrarlo contra los ataques
ajustaría la defensa a la batería y el ASR dejaría de medir resistencia.

Las capas deben ser genéricas, no ajustadas a la batería concreta de ataques:
un filtro escrito "a la medida" de ``attacks_v1.json`` inflaría artificialmente
la efectividad medida (ver la sección de Riesgos del plan de acción).

Estado: STUB (Fase 0). Implementación pendiente en la Fase 4 (rol R1 para
L1/L2/L4; R2 y R3 para L3 y L5). El system prompt se escribe en la Fase 1.
"""

from __future__ import annotations

from src.config import Config
from src.llm_client import LLMClient
from src.prompts import Prompts


def respond(
    user_input: str,
    client: LLMClient | None = None,
    prompts: Prompts | None = None,
    config: Config | None = None,
) -> dict:
    """Responde a ``user_input`` aplicando las 5 capas de defensa (condición B).

    Firma idéntica a :func:`src.chatbot_a.respond`, opcionales incluidos: el
    runner reutiliza un mismo ``LLMClient`` durante toda la corrida —para no
    reiniciar su espaciado de rate limit en cada interacción— y los tests
    inyectan dobles por ahí.

    Args:
        user_input: texto del usuario (ataque o prompt benigno), sin confianza.
        client: cliente LLM a usar. Por defecto, uno nuevo con la config activa.
        prompts: prompts ya cargados. Por defecto, los del repositorio.
        config: configuración a usar. Por defecto, la del repositorio.

    Returns:
        dict con las mismas diez claves que la condición A (ver
        :func:`src.chatbot_a.respond`, que documenta el contrato completo):

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
        * ``model_reported`` (str | None): modelo que reportó la API; ``None`` si
          L3 bloqueó y no hubo llamada.
        * ``truncated`` (bool): si la respuesta se cortó por ``max_tokens``.
        * ``reasoning`` (str | None): razonamiento interno del modelo. Se registra
          para el análisis cualitativo, pero NO se muestra al usuario ni se usa
          para clasificar: el usuario no lo ve, así que no puede ser una fuga.

    Raises:
        NotImplementedError: stub de la Fase 0.
        src.llm_client.LLMCallError: (una vez implementado) si la API falla tras
            los reintentos.
    """
    raise NotImplementedError("Condición B pendiente: se implementa en la Fase 4.")
