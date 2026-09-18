"""Cliente LLM: la ÚNICA puerta del proyecto hacia la API del proveedor.

Todo el resto del código (chatbot A, chatbot B, runner, smoke test) llama al
modelo a través de :class:`LLMClient`. Centralizar aquí las llamadas garantiza
que las dos condiciones experimentales se ejecuten con parámetros idénticos: si
cada módulo hablara con la API por su cuenta, cualquier diferencia accidental de
``temperature`` o ``max_tokens`` se convertiría en una variable de confusión.

Responsabilidades:

* Aplicar SIEMPRE los parámetros de ``config/experiment.yaml`` —incluidos
  ``reasoning_effort`` e ``include_reasoning``, que viajan en ``extra_body``
  cuando el SDK no los tipa—. No se pueden sobreescribir por llamada: son
  variables controladas, no opciones.
* Reintentar con backoff exponencial ante 429, errores 5xx y fallos de red.
* Reportar el modelo que la API dice haber usado (``model_reported``), que es
  el identificador exacto que debe citarse en la Tabla 6 del artículo.
* Medir la latencia de la llamada exitosa.

El espaciado entre llamadas NO vive aquí: lo aplica quien orquesta la corrida
(:mod:`src.runner`), entre interacciones, con :class:`Pacer`. El motivo es que
dormir dentro de ``chat()`` metía la espera dentro de ``respond()``, y
``latency_ms`` —que cronometra ``respond()`` de punta a punta— acababa midiendo
sobre todo el rate limit en vez del trabajo del chatbot. Con 12 s de espaciado,
la condición B llegó a parecer más rápida que la A en el piloto del 18-sep-2026,
porque sus interacciones bloqueadas por L3 no llamaban a la API y no esperaban.
Ver ``docs/proceso/incidencias.md``, entrada B-02.

El proveedor es intercambiable: Groq y Gemini exponen endpoints compatibles con
OpenAI, así que basta cambiar ``base_url``/``model`` en el YAML (o ``LLM_BASE_URL``
en ``.env``) sin tocar este archivo.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)

from src.config import Config, get_config

logger = logging.getLogger(__name__)

#: Códigos HTTP que justifican reintentar (el problema es transitorio).
#:
#: CUIDADO con el 429: casi siempre es transitorio, pero Groq lo usa también
#: para un rechazo PERMANENTE, cuando ``max_tokens`` supera el límite de tokens
#: de salida por minuto de la cuenta (OTPM). Ese caso no mejora reintentando:
#: agota los reintentos y acaba en LLMCallError, siete llamadas por interacción.
#: El mensaje lo distingue ("Request too large ... reduce max_tokens"). La
#: defensa está en la config: ``max_tokens`` debe quedar por debajo del OTPM
#: (ver config/experiment.yaml y tests/test_config.py).
RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})

#: Tope de espera por reintento, para que el backoff no se dispare sin control.
MAX_BACKOFF_SECONDS = 60.0

#: Nombres bajo los que un proveedor puede devolver el razonamiento del modelo.
#: Groq usa "reasoning"; otros endpoints compatibles usan "reasoning_content".
REASONING_FIELDS = ("reasoning", "reasoning_content")


class LLMCallError(RuntimeError):
    """La llamada a la API no se pudo completar.

    El runner debe registrar estas interacciones como ``"error"`` y NO como
    "el ataque falló": un timeout no es evidencia de que la defensa funcionó.
    """


class LLMClient:
    """Envoltorio fino y disciplinado sobre el SDK de OpenAI.

    Args:
        config: configuración a usar. Por defecto, la de ``config/experiment.yaml``.
        client: cliente ya construido (los tests inyectan aquí un doble).
    """

    def __init__(self, config: Config | None = None, client: Any | None = None) -> None:
        self.config = config or get_config()
        self._client = client or OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )
        # Parámetros extra del modelo, resueltos una sola vez: son variables
        # controladas y no cambian entre llamadas.
        inference = self.config.inference
        self._extra_params: dict[str, Any] = {}
        if inference.reasoning_effort is not None:
            self._extra_params["reasoning_effort"] = inference.reasoning_effort
        if inference.include_reasoning is not None:
            # El SDK de OpenAI no tipa include_reasoning (es propio de Groq):
            # va en extra_body, que el SDK envía tal cual en el cuerpo JSON.
            self._extra_params["extra_body"] = {
                "include_reasoning": inference.include_reasoning
            }

        # Generador propio: no tocamos el estado del `random` global, que el
        # runner usa con `execution_seed` para el orden de ejecución.
        self._jitter = random.Random(0xC0FFEE)

    # -- API pública --------------------------------------------------------

    def chat(self, messages: list[dict]) -> dict:
        """Envía ``messages`` al modelo y devuelve la respuesta más su telemetría.

        Args:
            messages: lista de mensajes estilo OpenAI, p. ej.
                ``[{"role": "system", "content": "..."},
                   {"role": "user", "content": "..."}]``.
                La condición A usará un único mensaje; la B, ``system`` + ``user``
                separados (capa L1).

        Returns:
            dict con las claves:

            * ``text`` (str): contenido de la respuesta del modelo.
            * ``model_reported`` (str): modelo que la API dice haber usado. Puede
              diferir del de la config (alias, versiones fechadas); es el que se
              cita en el artículo.
            * ``tokens_in`` (int | None): tokens del prompt. ``None`` si la API no
              reportó uso (no se inventa un 0: falsearía la métrica de sobrecosto).
            * ``tokens_out`` (int | None): tokens generados.
            * ``latency_ms`` (float): duración de la llamada exitosa, en milisegundos.
              No incluye esperas de rate limit ni intentos fallidos.
            * ``finish_reason`` (str | None): ``"stop"``, ``"length"``, etc.
            * ``truncated`` (bool): ``True`` si ``finish_reason == "length"``. Una
              respuesta truncada no puede analizarse como si estuviera completa:
              una fuga podría haberse quedado a medio escribir. El clasificador
              debe tratarla aparte, no como ataque fallido.
            * ``reasoning`` (str | None): razonamiento interno del modelo, si el
              proveedor lo devolvió. Nunca se mezcla con ``text``: el usuario del
              chatbot no lo ve, así que no cuenta como fuga; pero se registra
              porque ayuda a explicar por qué una inyección funcionó o no.

        Raises:
            LLMCallError: si se agotaron los reintentos, o ante un error no
                recuperable (credenciales inválidas, petición malformada).
            ValueError: si ``messages`` está vacío o malformado.
        """
        self._validate(messages)
        rl = self.config.rate_limit
        last_error: Exception | None = None

        # max_retries reintentos => max_retries + 1 intentos en total.
        for attempt in range(rl.max_retries + 1):
            try:
                started = time.perf_counter()
                response = self._client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.inference.temperature,
                    top_p=self.config.inference.top_p,
                    max_tokens=self.config.inference.max_tokens,
                    **self._extra_params,
                )
                latency_ms = (time.perf_counter() - started) * 1000.0
            except (RateLimitError, APITimeoutError, APIConnectionError) as exc:
                last_error = exc
                if attempt == rl.max_retries:
                    break
                self._sleep_before_retry(attempt, exc)
                continue
            except APIStatusError as exc:
                last_error = exc
                if exc.status_code not in RETRYABLE_STATUS_CODES:
                    # 401, 400, 404...: reintentar no arregla nada.
                    raise LLMCallError(
                        f"Error no recuperable de la API "
                        f"(HTTP {exc.status_code}): {exc}"
                    ) from exc
                if attempt == rl.max_retries:
                    break
                self._sleep_before_retry(attempt, exc)
                continue
            except OpenAIError as exc:
                # Error de cliente/SDK (p. ej. base_url inválida): no se reintenta.
                raise LLMCallError(f"Error del cliente LLM: {exc}") from exc

            return self._to_result(response, latency_ms)

        raise LLMCallError(
            f"La llamada falló tras {rl.max_retries + 1} intentos "
            f"(modelo={self.config.model}, proveedor={self.config.provider}). "
            f"Último error: {last_error}"
        ) from last_error

    # -- Internos -----------------------------------------------------------

    @staticmethod
    def _validate(messages: list[dict]) -> None:
        """Valida la forma de ``messages`` antes de gastar una llamada."""
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages debe ser una lista no vacía de mensajes.")
        for i, message in enumerate(messages):
            if not isinstance(message, dict):
                raise ValueError(f"messages[{i}] debe ser un dict.")
            if "role" not in message or "content" not in message:
                raise ValueError(f"messages[{i}] necesita las claves 'role' y 'content'.")

    def _sleep_before_retry(self, attempt: int, exc: Exception) -> None:
        """Espera exponencial (con jitter) antes del siguiente intento."""
        rl = self.config.rate_limit
        delay = min(rl.backoff_base_seconds ** (attempt + 1), MAX_BACKOFF_SECONDS)
        retry_after = self._retry_after(exc)
        if retry_after is not None:
            delay = min(max(delay, retry_after), MAX_BACKOFF_SECONDS)
        delay += self._jitter.uniform(0.0, 0.5)  # evita sincronizar reintentos
        logger.warning(
            "Intento %d/%d falló (%s). Reintentando en %.2f s.",
            attempt + 1,
            rl.max_retries + 1,
            type(exc).__name__,
            delay,
        )
        time.sleep(delay)

    @staticmethod
    def _retry_after(exc: Exception) -> float | None:
        """Lee la cabecera ``Retry-After`` si el proveedor la envió."""
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        if not headers:
            return None
        try:
            return float(headers.get("retry-after"))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_reasoning(message: Any) -> str | None:
        """Devuelve el razonamiento del modelo si el proveedor lo envió.

        Se busca tanto en los atributos tipados como en ``model_extra``, donde el
        SDK deja los campos que no conoce. Devuelve ``None`` si no hay ninguno o
        si viene vacío.
        """
        for campo in REASONING_FIELDS:
            valor = getattr(message, campo, None)
            if isinstance(valor, str) and valor.strip():
                return valor
        extra = getattr(message, "model_extra", None) or {}
        for campo in REASONING_FIELDS:
            valor = extra.get(campo)
            if isinstance(valor, str) and valor.strip():
                return valor
        return None

    def _to_result(self, response: Any, latency_ms: float) -> dict:
        """Normaliza la respuesta del SDK al dict que consume todo el proyecto."""
        choices = getattr(response, "choices", None) or []
        if not choices:
            raise LLMCallError("La API devolvió una respuesta sin 'choices'.")

        choice = choices[0]
        message = getattr(choice, "message", None)
        text = getattr(message, "content", None) or ""
        finish_reason = getattr(choice, "finish_reason", None)
        usage = getattr(response, "usage", None)
        if usage is None:
            logger.warning("La API no reportó 'usage'; tokens_in/tokens_out serán None.")

        # El razonamiento NUNCA se mezcla con el texto: el usuario del chatbot no
        # lo ve, así que no puede contar como fuga. Pero se registra aparte,
        # porque puede explicar por qué una inyección funcionó o no.
        reasoning = self._extract_reasoning(message)
        if reasoning is not None and self.config.inference.include_reasoning is False:
            logger.warning(
                "El modelo devolvió razonamiento pese a include_reasoning=false "
                "(%d caracteres). Se registra aparte, fuera de 'text'.",
                len(reasoning),
            )

        # Una respuesta truncada no puede analizarse como si estuviera completa:
        # una fuga podría haberse quedado a medio escribir.
        truncated = finish_reason == "length"
        if truncated:
            logger.warning(
                "Respuesta TRUNCADA (finish_reason='length') con max_tokens=%d. "
                "En un modelo de razonamiento el presupuesto lo consumen también "
                "los tokens de razonamiento. Texto devuelto: %d caracteres.",
                self.config.inference.max_tokens,
                len(text),
            )

        result = {
            "text": text,
            "model_reported": getattr(response, "model", None) or self.config.model,
            "tokens_in": getattr(usage, "prompt_tokens", None) if usage else None,
            "tokens_out": getattr(usage, "completion_tokens", None) if usage else None,
            "latency_ms": latency_ms,
            "finish_reason": finish_reason,
            "truncated": truncated,
            "reasoning": reasoning,
        }
        logger.info(
            "Llamada OK: modelo=%s tokens_in=%s tokens_out=%s latencia=%.0f ms "
            "finish=%s truncada=%s",
            result["model_reported"],
            result["tokens_in"],
            result["tokens_out"],
            latency_ms,
            finish_reason,
            truncated,
        )
        return result


class Pacer:
    """Espacia las llamadas a la API, FUERA del cronómetro de ``respond()``.

    Vive aquí, junto al cliente, porque es política de rate limit; pero lo usa
    quien orquesta una corrida —:mod:`src.runner`, ``scripts/calibrate_l5.py``—
    entre interacciones, nunca dentro de ellas.

    Esa separación es la corrección del bug B-02: cuando el espaciado dormía
    dentro de ``LLMClient.chat()``, la espera quedaba dentro de ``respond()`` y
    ``latency_ms`` medía sobre todo el rate limit. Peor aún, lo medía de forma
    desigual entre condiciones: las interacciones que L3 bloquea no llaman a la
    API y por tanto no esperaban, así que la condición defendida parecía más
    rápida que la línea base.

    Args:
        min_seconds: separación mínima entre dos llamadas consecutivas. Con 0 o
            menos, no espera nunca (útil en ``--dry-run`` y en los tests).
    """

    def __init__(self, min_seconds: float) -> None:
        self.min_seconds = min_seconds
        self._last_at: float | None = None
        self.total_slept = 0.0

    def wait(self) -> float:
        """Duerme lo que falte para respetar la separación. Devuelve cuánto durmió.

        Se usa ``time.monotonic`` (no ``time.time``) para que un ajuste del reloj
        del sistema no altere el espaciado.
        """
        if self._last_at is None or self.min_seconds <= 0:
            self._last_at = time.monotonic()
            return 0.0
        restante = self.min_seconds - (time.monotonic() - self._last_at)
        if restante > 0:
            logger.debug("Espaciado de rate limit: durmiendo %.2f s", restante)
            time.sleep(restante)
            self.total_slept += restante
        self._last_at = time.monotonic()
        return max(restante, 0.0)
