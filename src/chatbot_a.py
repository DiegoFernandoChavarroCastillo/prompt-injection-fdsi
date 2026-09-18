"""Condición A — chatbot BASELINE VULNERABLE (Fase 3).

Esta condición existe para medir el riesgo *sin* defensas: es el punto de
comparación contra el cual se reporta la reducción de ASR de la condición B.

Reproduce el Listing 1 del artículo (Sección III-C)::

    prompt = f\"\"\"{SYSTEM_PROMPT}
    Usuario: {user_input}
    Asistente:\"\"\"
    respuesta = llm.generate(prompt)
    return respuesta   # sin validacion de salida

Sobre una API de chat, esa concatenación plana se envía como **un único mensaje
con rol** ``user``, sin mensaje ``system``. Es intencional y es el núcleo del
experimento: al viajar todo en el mismo mensaje y con el mismo rol, el modelo no
tiene ninguna señal estructural que le permita distinguir la instrucción
legítima del operador de una instrucción inyectada por el cliente. Esa
indistinguibilidad es la vulnerabilidad OWASP LLM01 que el estudio mide.

NO "arreglar" esta condición. Poner el system prompt en un mensaje ``system``
propio sería implementar L1, es decir, convertir A en B y quedarse sin
comparación. Por el mismo motivo aquí no hay validación de entrada (L3) ni de
salida (L5), ni se toca la entrada del usuario: ni ``strip``, ni escape, ni
normalización Unicode. Los homóglifos cirílicos y los espacios de ancho cero de
A20 deben llegar al modelo byte a byte, porque justamente evaden filtros que
aquí no existen.
"""

from __future__ import annotations

import logging

from src.config import Config, get_config
from src.llm_client import LLMClient
from src.prompts import Prompts, load_prompts

logger = logging.getLogger(__name__)

#: Etiquetas del diálogo, tal como aparecen en el Listing 1.
USER_TAG = "Usuario:"
ASSISTANT_TAG = "Asistente:"


def build_prompt(system_prompt: str, user_input: str) -> str:
    """Concatena el prompt de la condición A exactamente como el Listing 1.

    Args:
        system_prompt: contenido de ``prompts/system_A.txt``, **sin** ``strip``.
            Ese archivo termina en salto de línea, así que el prompt resultante
            trae una línea en blanco antes de ``Usuario:``; se conserva porque
            el listing publicado interpola la cadena tal cual.
        user_input: entrada del cliente, literal y sin sanitizar.

    Returns:
        La cadena única que se envía al modelo.
    """
    return f"{system_prompt}\n{USER_TAG} {user_input}\n{ASSISTANT_TAG}"


def respond(
    user_input: str,
    client: LLMClient | None = None,
    prompts: Prompts | None = None,
    config: Config | None = None,
) -> dict:
    """Responde a ``user_input`` sin ninguna defensa (condición A).

    Firma compatible con :func:`src.chatbot_b.respond`: el runner debe poder
    tratar ambas condiciones de forma intercambiable. Los tres argumentos
    opcionales existen para inyectar dobles en los tests y para que el runner
    reutilice un mismo cliente durante toda la corrida, en lugar de reconstruirlo
    —y reiniciar su espaciado de rate limit— en cada interacción.

    Args:
        user_input: texto del usuario, tal cual viene de la batería (ataque o
            prompt benigno). No se sanitiza: ese es el punto de la condición A.
        client: cliente LLM a usar. Por defecto, uno nuevo con la config activa.
        prompts: prompts ya cargados. Por defecto, los del repositorio.
        config: configuración a usar. Por defecto, la del repositorio.

    Returns:
        dict con diez claves, las mismas que devuelve la condición B:

        * ``response`` (str): texto final entregado al usuario. En A es siempre
          igual a ``raw_model_output``: no hay validación de salida.
        * ``raw_model_output`` (str): salida cruda del modelo, antes de cualquier
          post-procesamiento. Es lo que audita el clasificador.
        * ``blocked_by`` (str | None): capa que bloqueó la interacción. En A es
          siempre ``None``; la clave existe para que el log tenga el mismo
          esquema en ambas condiciones.
        * ``sent_context`` (str): la cadena exacta que se envió al modelo, para
          poder auditar después qué vio realmente (evidencia del Anexo B).
        * ``tokens_in`` (int | None), ``tokens_out`` (int | None): uso reportado
          por la API; base del cálculo de sobrecosto entre A y B.
        * ``latency_ms`` (float): latencia de la llamada.
        * ``model_reported`` (str | None): modelo que reportó la API. Se registra
          por interacción para detectar un cambio de versión a media corrida.
        * ``truncated`` (bool): si la respuesta se cortó por ``max_tokens``. Una
          respuesta truncada no puede analizarse como completa.
        * ``reasoning`` (str | None): razonamiento interno del modelo. Se registra
          para el análisis cualitativo, pero el usuario no lo ve y por tanto el
          clasificador lo ignora: un canary ahí no es una fuga.

    Raises:
        src.llm_client.LLMCallError: si la API falla tras los reintentos. Se deja
            propagar a propósito: es el runner quien decide registrarla como
            ``status="error"``, y nunca como ataque fallido.
    """
    config = config or get_config()
    prompts = prompts or load_prompts(config)
    client = client or LLMClient(config)

    # Listing 1: system prompt y entrada del usuario en una sola cadena.
    prompt = build_prompt(prompts.system_A, user_input)

    # Un único mensaje, rol "user". No hay mensaje "system": esa separación es
    # precisamente la capa L1 que la condición A no tiene.
    result = client.chat([{"role": "user", "content": prompt}])

    text = result["text"]
    logger.debug(
        "Condición A: %d caracteres de contexto -> %d caracteres de respuesta",
        len(prompt),
        len(text),
    )

    return {
        # Sin validación de salida: lo que dijo el modelo es lo que recibe el
        # usuario. Las dos claves son iguales por construcción en esta condición.
        "response": text,
        "raw_model_output": text,
        "blocked_by": None,
        "sent_context": prompt,
        "tokens_in": result["tokens_in"],
        "tokens_out": result["tokens_out"],
        "latency_ms": result["latency_ms"],
        "model_reported": result["model_reported"],
        "truncated": result["truncated"],
        "reasoning": result["reasoning"],
    }
