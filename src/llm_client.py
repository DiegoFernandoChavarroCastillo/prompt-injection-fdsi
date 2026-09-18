"""Cliente LLM: la ÚNICA puerta del proyecto hacia la API del proveedor.

Todo el resto del código (chatbot A, chatbot B, runner, smoke test) llama al
modelo a través de :class:`LLMClient`. Centralizar aquí las llamadas garantiza
que las dos condiciones experimentales se ejecuten con parámetros idénticos: si
cada módulo hablara con la API por su cuenta, cualquier diferencia accidental de
``temperature`` o ``max_tokens`` se convertiría en una variable de confusión.

Responsabilidades:

* Aplicar SIEMPRE los parámetros de ``config/experiment.yaml``. No se pueden
  sobreescribir por llamada: son variables controladas, no opciones.
* Espaciar las llamadas (``min_seconds_between_calls``) para no gatillar el
  rate limit del proveedor.
* Reintentar con backoff exponencial ante 429, errores 5xx y fallos de red.
* Reportar el modelo que la API dice haber usado (``model_reported``), que es
  el identificador exacto que debe citarse en la Tabla 6 del artículo.
* Medir la latencia de la llamada exitosa.

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
RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})

#: Tope de espera por reintento, para que el backoff no se dispare sin control.
MAX_BACKOFF_SECONDS = 60.0


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
        # Instante (monotónico) en que terminó la última llamada; None = ninguna aún.
        self._last_call_at: float | None = None
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
            self._respect_min_spacing()
            try:
                started = time.perf_counter()
                response = self._client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.inference.temperature,
                    top_p=self.config.inference.top_p,
                    max_tokens=self.config.inference.max_tokens,
                )
                latency_ms = (time.perf_counter() - started) * 1000.0
            except (RateLimitError, APITimeoutError, APIConnectionError) as exc:
                last_error = exc
                self._last_call_at = time.monotonic()
                if attempt == rl.max_retries:
                    break
                self._sleep_before_retry(attempt, exc)
                continue
            except APIStatusError as exc:
                last_error = exc
                self._last_call_at = time.monotonic()
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

            self._last_call_at = time.monotonic()
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

    def _respect_min_spacing(self) -> None:
        """Duerme lo necesario para cumplir ``min_seconds_between_calls``.

        Se usa ``time.monotonic`` (no ``time.time``) para que un ajuste del reloj
        del sistema no altere el espaciado.
        """
        minimum = self.config.rate_limit.min_seconds_between_calls
        if self._last_call_at is None or minimum <= 0:
            return
        elapsed = time.monotonic() - self._last_call_at
        remaining = minimum - elapsed
        if remaining > 0:
            logger.debug("Espaciado de rate limit: durmiendo %.2f s", remaining)
            time.sleep(remaining)

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

    def _to_result(self, response: Any, latency_ms: float) -> dict:
        """Normaliza la respuesta del SDK al dict que consume todo el proyecto."""
        choices = getattr(response, "choices", None) or []
        if not choices:
            raise LLMCallError("La API devolvió una respuesta sin 'choices'.")

        choice = choices[0]
        text = getattr(choice.message, "content", None) or ""
        usage = getattr(response, "usage", None)
        if usage is None:
            logger.warning("La API no reportó 'usage'; tokens_in/tokens_out serán None.")

        result = {
            "text": text,
            "model_reported": getattr(response, "model", None) or self.config.model,
            "tokens_in": getattr(usage, "prompt_tokens", None) if usage else None,
            "tokens_out": getattr(usage, "completion_tokens", None) if usage else None,
            "latency_ms": latency_ms,
            "finish_reason": getattr(choice, "finish_reason", None),
        }
        logger.info(
            "Llamada OK: modelo=%s tokens_in=%s tokens_out=%s latencia=%.0f ms finish=%s",
            result["model_reported"],
            result["tokens_in"],
            result["tokens_out"],
            latency_ms,
            result["finish_reason"],
        )
        return result
