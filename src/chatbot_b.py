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
  trae el propio delimitador —o una variante suya— se sustituye por
  ``[marca eliminada]`` antes de envolverla: si no, el atacante podría cerrar
  el bloque de datos y escribir fuera de él. La declaración de que ese bloque
  es dato y no instrucción está en la sección ``[SEGURIDAD — ENTRADA DEL
  USUARIO]`` de ``prompts/system_B.txt``.
* **L2 — Sándwich.** ``prompts/l2_reminder.txt`` se reinyecta DESPUÉS del
  delimitador de cierre, dentro del MISMO mensaje ``user``, para que la última
  instrucción del contexto sea del operador y no del atacante.
* **L3 — Filtro de entrada.** Bloquea antes de gastar una llamada a la API;
  ver :mod:`src.defenses.l3_input_filter`.
* **L4 — Anti-leaking.** Ya está en ``prompts/system_B.txt`` (Fase 1): las
  secciones ``[SEGURIDAD — CONFIDENCIALIDAD]`` y ``[EJEMPLOS DE RESPUESTA]``.
  Aquí solo hay que verificar que se esté enviando completo.
* **L5 — Validación de salida.** Última red: canary, solapamiento de 5-gramas
  contra :data:`src.prompts.PROTECTED_SECTIONS` y marcadores de rol o de
  compromiso comercial; ver :mod:`src.defenses.l5_output_validator`.

REGLA ANTISESGO (Fase 4)
------------------------
Durante toda la Fase 4, la condición B **solo** se prueba con prompts benignos y
con ataques de desarrollo escritos a mano. **Nunca** con los 20 ataques de
``data/attacks_v1.json``, y ningún test de B puede importarlos.

El motivo es que si las capas se ajustan mirando los ataques concretos con los
que después se las evalúa, el ASR medido ya no dice cuánto resiste la defensa:
dice cuánto se la afinó contra esa batería, y no generaliza a nada. La batería
está congelada y preregistrada (tag ``battery-v1``) precisamente para poder
afirmar que no se tocó; esta regla es la mitad complementaria, la que garantiza
que tampoco se tocó la defensa mirándola. Lo comprueba
``tests/test_antisesgo.py``.

TODO (Fase 4c): los delimitadores ``<<<USER_DATA_a91f>>>`` y
``<<</USER_DATA_a91f>>>`` están escritos dentro de ``system_B.txt``, así que un
ataque puede extraerlos sin adivinarlos. L5 debe tratar su aparición en la
salida como señal de fuga, igual que el canary. Y el umbral de n-gramas se
calibra con los benignos, nunca con los ataques: calibrarlo contra los ataques
ajustaría la defensa a la batería y el ASR dejaría de medir resistencia.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from src.config import Config, get_config
from src.defenses import l3_input_filter, l5_output_validator
from src.llm_client import LLMClient
from src.prompts import Prompts, load_prompts

logger = logging.getLogger(__name__)

#: Marcas de L4/L1 que encierran la entrada no confiable del cliente.
OPEN_DELIMITER = "<<<USER_DATA_a91f>>>"
CLOSE_DELIMITER = "<<</USER_DATA_a91f>>>"

#: Texto con el que se sustituye cualquier marca que venga en la entrada.
ESCAPE_REPLACEMENT = "[marca eliminada]"

#: Reconoce cualquier variante de las marcas dentro de la entrada del usuario.
#:
#: Deliberadamente amplio: no basta con buscar las dos cadenas exactas, porque
#: al atacante le vale cualquier cosa que el modelo interprete como cierre del
#: bloque de datos. Cubre la barra de cierre, mayúsculas y minúsculas, espacios
#: internos y cualquier contenido alrededor de ``USER_DATA`` (incluido un
#: identificador distinto del nuestro, que el modelo podría leer igual).
#: Un falso positivo aquí solo cuesta un ``[marca eliminada]`` en una consulta
#: rarísima; un falso negativo deja escapar del bloque al atacante.
DELIMITER_PATTERN = re.compile(r"<<<[^>]*?USER[\s_]*DATA[^>]*>>>", re.IGNORECASE)


def escape_delimiters(user_input: str) -> tuple[str, int]:
    """Neutraliza las marcas de L1 que vengan en la entrada del cliente.

    Args:
        user_input: entrada cruda del cliente.

    Returns:
        ``(texto_escapado, cuántas marcas se sustituyeron)``.

    Solo toca las marcas. NO normaliza el texto: los homóglifos cirílicos y los
    espacios de ancho cero deben llegar intactos al modelo, porque normalizarlos
    es trabajo de L3 y hacerlo aquí cambiaría el ataque antes de medirlo.
    """
    return DELIMITER_PATTERN.subn(ESCAPE_REPLACEMENT, user_input)


def build_messages(system_b: str, user_input: str, l2_reminder: str) -> tuple[list[dict], int]:
    """Arma el contexto de la condición B: L1 + L4 en ``system``, L1 + L2 en ``user``.

    Args:
        system_b: contenido de ``prompts/system_B.txt``, verbatim (incluye L4).
        user_input: entrada cruda del cliente; se escapa aquí.
        l2_reminder: contenido de ``prompts/l2_reminder.txt``.

    Returns:
        ``(messages, marcas_escapadas)``, con ``messages`` en el formato del SDK.
    """
    escapado, escapadas = escape_delimiters(user_input)
    contenido_usuario = (
        f"{OPEN_DELIMITER}\n{escapado}\n{CLOSE_DELIMITER}\n\n{l2_reminder}"
    )
    messages = [
        {"role": "system", "content": system_b},
        {"role": "user", "content": contenido_usuario},
    ]
    return messages, escapadas


def format_context(messages: list[dict]) -> str:
    """Serializa los mensajes enviados de forma legible, para el log.

    El formato es ``[rol]`` seguido del contenido. Sirve para auditar en el
    Anexo B qué vio exactamente el modelo, sin tener que releer el JSON crudo.
    """
    return "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in messages)


def respond(
    user_input: str,
    client: LLMClient | None = None,
    prompts: Prompts | None = None,
    config: Config | None = None,
    l3: Any | None = None,
    l5: Any | None = None,
) -> dict:
    """Responde a ``user_input`` aplicando las 5 capas de defensa (condición B).

    Firma compatible con :func:`src.chatbot_a.respond`: el runner debe poder
    tratar ambas condiciones de forma intercambiable. Los opcionales existen
    para inyectar dobles en los tests y para que el runner reutilice un mismo
    ``LLMClient`` durante toda la corrida, en lugar de reconstruirlo —y
    reiniciar su espaciado de rate limit— en cada interacción.

    Args:
        user_input: texto del usuario (ataque o prompt benigno), sin confianza.
        client: cliente LLM a usar. Por defecto, uno nuevo con la config activa.
        prompts: prompts ya cargados. Por defecto, los del repositorio.
        config: configuración a usar. Por defecto, la del repositorio.
        l3: módulo con ``check_input(text)``. Por defecto,
            :mod:`src.defenses.l3_input_filter`.
        l5: módulo con ``validate_output(text)``. Por defecto,
            :mod:`src.defenses.l5_output_validator`.

    Returns:
        dict con las mismas doce claves que la condición A (ver
        :func:`src.chatbot_a.respond`, que documenta el contrato completo):

        * ``response`` (str): texto entregado al usuario. Si L3 o L5 bloquearon,
          es el mensaje de rechazo, no la salida del modelo.
        * ``raw_model_output`` (str | None): salida cruda del modelo antes de L5,
          o ``None`` si L3 bloqueó y nunca se llamó a la API.
        * ``blocked_by`` (str | None): ``"L3:<regla>"``, ``"L5:<verificación>"``
          o ``None``. Es la rama objetiva que el clasificador puede etiquetar sin
          juicio humano. Es interno: el usuario recibe el mismo texto en los dos
          casos y no puede deducir qué capa actuó.
        * ``sent_context`` (str): los mensajes enviados, serializados por rol.
          Cadena vacía si L3 bloqueó y no se envió nada.
        * ``tokens_in`` (int | None), ``tokens_out`` (int | None): uso de la API;
          ``None`` si L3 bloqueó y no hubo llamada.
        * ``latency_ms`` (float): tiempo TOTAL de ``respond()``, de entrada a
          salida, capas incluidas.
        * ``api_latency_ms`` (float | None): latencia de la llamada al modelo,
          tal como la mide :class:`src.llm_client.LLMClient`. ``None`` si no
          hubo llamada (L3 bloqueó en la condición B).

          El sobrecosto de B se analiza con las dos: la diferencia en
          ``api_latency_ms`` entre B y A refleja el contexto más largo que
          procesa el modelo, y la diferencia ``latency_ms - api_latency_ms``
          refleja el costo de las capas deterministas (L1, L3, L5), que es
          trabajo local y no depende del proveedor. Con una sola cifra ambos
          efectos quedarían mezclados y el sobrecosto sería inatribuible.
        * ``model_reported`` (str | None): modelo que reportó la API; ``None`` si
          L3 bloqueó.
        * ``truncated`` (bool): si la respuesta se cortó por ``max_tokens``.
        * ``reasoning`` (str | None): razonamiento interno del modelo. Se registra
          para el análisis cualitativo, pero NO se muestra al usuario ni se usa
          para clasificar: el usuario no lo ve, así que no puede ser una fuga.
        * ``defense_trace`` (dict): qué hizo cada capa —``l1_delimiters_escaped``,
          el dict de L3 y el de L5—, para poder auditar una decisión sin repetir
          la llamada.

    Raises:
        NotImplementedError: mientras L3 o L5 sigan siendo stubs. Se deja
            propagar a propósito: silenciarla dejaría correr una "condición B"
            sin filtro ni validador, y los resultados parecerían válidos.
        src.llm_client.LLMCallError: si la API falla tras los reintentos. La
            registra el runner como ``status="error"``, nunca como ataque fallido.
    """
    config = config or get_config()
    prompts = prompts or load_prompts(config)
    client = client or LLMClient(config)
    l3 = l3 or l3_input_filter
    l5 = l5 or l5_output_validator

    started = time.perf_counter()

    # -- L3: filtrar antes de gastar una llamada a la API --------------------
    l3_result = l3.check_input(user_input)
    if l3_result["blocked"]:
        logger.info("Condición B: L3 bloqueó la entrada (regla=%s)", l3_result["rule"])
        return {
            "response": prompts.l3_rejection,
            "raw_model_output": None,
            "blocked_by": f"L3:{l3_result['rule']}",
            "sent_context": "",
            "tokens_in": None,
            "tokens_out": None,
            "latency_ms": (time.perf_counter() - started) * 1000.0,
            # No hubo llamada al modelo: todo el tiempo lo consumió L3.
            "api_latency_ms": None,
            "model_reported": None,
            "truncated": False,
            "reasoning": None,
            "defense_trace": {
                "l1_delimiters_escaped": 0,
                "l3": l3_result,
                "l5": None,  # nunca se llegó a ejecutar
            },
        }

    # -- L1 + L2 + L4: construir el contexto ---------------------------------
    messages, escapadas = build_messages(prompts.system_B, user_input, prompts.l2_reminder)
    if escapadas:
        logger.warning(
            "Condición B: L1 neutralizó %d marca(s) de delimitador en la entrada.",
            escapadas,
        )

    # -- LLM -----------------------------------------------------------------
    result = client.chat(messages)
    raw_model_output = result["text"]

    # -- L5: validar antes de entregar ---------------------------------------
    l5_result = l5.validate_output(raw_model_output)
    if l5_result["passed"]:
        response = raw_model_output
        blocked_by = None
    else:
        logger.info("Condición B: L5 retuvo la salida (check=%s)", l5_result["check"])
        response = prompts.l5_fallback
        blocked_by = f"L5:{l5_result['check']}"

    return {
        "response": response,
        # La salida cruda se conserva aunque L5 la haya retenido: es lo que
        # audita el clasificador para saber si la inyección llegó a funcionar.
        "raw_model_output": raw_model_output,
        "blocked_by": blocked_by,
        "sent_context": format_context(messages),
        "tokens_in": result["tokens_in"],
        "tokens_out": result["tokens_out"],
        "latency_ms": (time.perf_counter() - started) * 1000.0,
        "api_latency_ms": result["latency_ms"],
        "model_reported": result["model_reported"],
        "truncated": result["truncated"],
        "reasoning": result["reasoning"],
        "defense_trace": {
            "l1_delimiters_escaped": escapadas,
            "l3": l3_result,
            "l5": l5_result,
        },
    }
