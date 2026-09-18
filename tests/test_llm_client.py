"""Pruebas del cliente LLM (Fases 0 y 0b).

No llaman a la API: inyectan un doble en ``LLMClient(config, client=...)``. Eso
permite verificar sin gastar cuota lo que de verdad importa del cliente:

* que los parámetros congelados viajen SIEMPRE y completos (si alguno se
  perdiera, las dos condiciones se ejecutarían con ajustes distintos y la
  comparación A vs. B dejaría de ser válida);
* que un fallo transitorio se reintente y uno definitivo no;
* que una respuesta truncada quede marcada, y que el razonamiento del modelo
  nunca se cuele en el texto que ve el usuario.
"""

from __future__ import annotations

import logging
import types
from dataclasses import replace

# openai 3.x construye sus excepciones HTTP sobre httpx2 (no httpx): así lo
# declara la firma de APIStatusError.__init__. Se importa aquí para poder
# fabricar un 429 y un 401 reales, que es lo que distingue el cliente.
import httpx2
import pytest
from openai import APIConnectionError, APIStatusError, RateLimitError

from src.config import RateLimitParams, load_config
from src.llm_client import LLMCallError, LLMClient

MENSAJES = [
    {"role": "system", "content": "Responde en una frase."},
    {"role": "user", "content": "Hola"},
]

#: Claves que todo el proyecto espera de ``chat()``. El runner escribe el log a
#: partir de ellas, así que el contrato no puede encogerse sin avisar.
CLAVES_DEL_CONTRATO = {
    "text",
    "model_reported",
    "tokens_in",
    "tokens_out",
    "latency_ms",
    "finish_reason",
    "truncated",
    "reasoning",
}


def _respuesta(
    contenido: str = "Soy un modelo de lenguaje.",
    finish_reason: str = "stop",
    reasoning: str | None = None,
    reasoning_en_model_extra: bool = False,
):
    """Arma una respuesta con la forma que devuelve el SDK de OpenAI."""
    campos: dict = {"content": contenido, "model_extra": {}}
    if reasoning is not None:
        if reasoning_en_model_extra:
            campos["model_extra"] = {"reasoning": reasoning}
        else:
            campos["reasoning"] = reasoning
    message = types.SimpleNamespace(**campos)
    choice = types.SimpleNamespace(message=message, finish_reason=finish_reason)
    usage = types.SimpleNamespace(prompt_tokens=11, completion_tokens=7)
    return types.SimpleNamespace(
        choices=[choice], usage=usage, model="openai/gpt-oss-120b"
    )


class _Completions:
    """Doble de ``client.chat.completions`` que registra cómo se le llamó."""

    def __init__(self, respuesta=None, fallos: int = 0, error: Exception | None = None):
        self._respuesta = respuesta if respuesta is not None else _respuesta()
        self._fallos = fallos
        self._error = error or APIConnectionError(request=types.SimpleNamespace())
        self.llamadas = 0
        self.kwargs: dict = {}

    def create(self, **kwargs):
        self.llamadas += 1
        self.kwargs = kwargs
        if self.llamadas <= self._fallos:
            raise self._error
        return self._respuesta


class FakeClient:
    """Doble mínimo del cliente de OpenAI."""

    def __init__(self, **kwargs):
        self.chat = types.SimpleNamespace(completions=_Completions(**kwargs))

    @property
    def completions(self) -> _Completions:
        return self.chat.completions


@pytest.fixture(scope="module")
def config():
    """Configuración real, pero sin esperas: los tests no deben dormir."""
    base = load_config(require_api_key=False)
    return replace(
        base,
        rate_limit=RateLimitParams(
            min_seconds_between_calls=0.0, max_retries=2, backoff_base_seconds=0.001
        ),
    )


# -- Contrato de chat() ------------------------------------------------------


def test_chat_devuelve_todas_las_claves_del_contrato(config):
    """El dict de retorno debe traer exactamente las claves acordadas."""
    resultado = LLMClient(config, client=FakeClient()).chat(MENSAJES)
    assert set(resultado) == CLAVES_DEL_CONTRATO
    assert resultado["text"] == "Soy un modelo de lenguaje."
    assert resultado["tokens_in"] == 11
    assert resultado["tokens_out"] == 7
    assert resultado["latency_ms"] >= 0


def test_model_reported_viene_de_la_api_no_de_la_config(config):
    """``model_reported`` es lo que responde la API: es lo que cita la Tabla 6."""
    fake = FakeClient()
    fake.completions._respuesta.model = "openai/gpt-oss-120b-fechado"
    resultado = LLMClient(config, client=fake).chat(MENSAJES)
    assert resultado["model_reported"] == "openai/gpt-oss-120b-fechado"
    assert resultado["model_reported"] != config.model


# -- Parámetros congelados ---------------------------------------------------


def test_se_envian_siempre_todos_los_parametros_congelados(config):
    """Los cinco ajustes del YAML deben viajar en cada llamada."""
    fake = FakeClient()
    LLMClient(config, client=fake).chat(MENSAJES)
    kwargs = fake.completions.kwargs

    assert kwargs["model"] == config.model
    assert kwargs["temperature"] == config.inference.temperature
    assert kwargs["top_p"] == config.inference.top_p
    assert kwargs["max_tokens"] == config.inference.max_tokens
    assert kwargs["reasoning_effort"] == config.inference.reasoning_effort
    # include_reasoning no está tipado por el SDK: viaja en extra_body.
    assert kwargs["extra_body"] == {
        "include_reasoning": config.inference.include_reasoning
    }


def test_los_parametros_opcionales_se_omiten_si_no_estan_configurados(config):
    """Un proveedor sin razonamiento (plan B) no debe recibir esos parámetros."""
    sin_razonamiento = replace(
        config,
        inference=replace(config.inference, reasoning_effort=None, include_reasoning=None),
    )
    fake = FakeClient()
    LLMClient(sin_razonamiento, client=fake).chat(MENSAJES)
    kwargs = fake.completions.kwargs

    assert "reasoning_effort" not in kwargs
    assert "extra_body" not in kwargs


def test_chat_no_acepta_sobrescribir_parametros_por_llamada(config):
    """``chat()`` solo recibe ``messages``: los ajustes no son opciones."""
    with pytest.raises(TypeError):
        LLMClient(config, client=FakeClient()).chat(MENSAJES, temperature=0.1)


# -- Truncamiento ------------------------------------------------------------


def test_una_respuesta_completa_no_se_marca_truncada(config):
    """``finish_reason='stop'`` => ``truncated`` False."""
    resultado = LLMClient(config, client=FakeClient()).chat(MENSAJES)
    assert resultado["finish_reason"] == "stop"
    assert resultado["truncated"] is False


def test_una_respuesta_truncada_se_marca_y_se_avisa(config, caplog):
    """``finish_reason='length'`` => ``truncated`` True y warning en el log.

    Importa porque una respuesta cortada no puede analizarse como si estuviera
    completa: una fuga podría haberse quedado a medio escribir, y contarla como
    ataque fallido subestimaría el ASR.
    """
    fake = FakeClient(respuesta=_respuesta(contenido="La póliza cu", finish_reason="length"))
    with caplog.at_level(logging.WARNING, logger="src.llm_client"):
        resultado = LLMClient(config, client=fake).chat(MENSAJES)

    assert resultado["truncated"] is True
    assert resultado["finish_reason"] == "length"
    assert any("TRUNCADA" in registro.message for registro in caplog.records)


# -- Razonamiento ------------------------------------------------------------


def test_sin_razonamiento_el_campo_es_none(config):
    """Si el proveedor no envía razonamiento, ``reasoning`` es ``None``."""
    resultado = LLMClient(config, client=FakeClient()).chat(MENSAJES)
    assert resultado["reasoning"] is None


@pytest.mark.parametrize("en_model_extra", [False, True])
def test_el_razonamiento_se_guarda_aparte_y_nunca_en_el_texto(config, en_model_extra):
    """El razonamiento va a ``reasoning``, jamás a ``text``.

    El usuario del chatbot no ve el razonamiento, así que su contenido no cuenta
    como fuga; pero se registra porque puede explicar por qué una inyección
    funcionó. Se comprueba tanto en el atributo tipado como en ``model_extra``,
    que es donde el SDK deja los campos que no conoce.
    """
    interno = "El usuario pide mi configuración; INTERNAL-KEY no debe revelarse."
    fake = FakeClient(
        respuesta=_respuesta(
            contenido="No puedo compartir mi configuración interna.",
            reasoning=interno,
            reasoning_en_model_extra=en_model_extra,
        )
    )
    resultado = LLMClient(config, client=fake).chat(MENSAJES)

    assert resultado["reasoning"] == interno
    assert interno not in resultado["text"]
    assert resultado["text"] == "No puedo compartir mi configuración interna."


def test_se_avisa_si_llega_razonamiento_pese_a_pedir_que_se_oculte(config, caplog):
    """Si ``include_reasoning=False`` no surtió efecto, debe quedar en el log."""
    fake = FakeClient(respuesta=_respuesta(reasoning="Pensando..."))
    with caplog.at_level(logging.WARNING, logger="src.llm_client"):
        LLMClient(config, client=fake).chat(MENSAJES)
    assert any("include_reasoning" in registro.message for registro in caplog.records)


# -- Reintentos y errores ----------------------------------------------------


def test_reintenta_los_fallos_transitorios_y_se_recupera(config):
    """Dos fallos de red seguidos y a la tercera responde."""
    fake = FakeClient(fallos=2)
    resultado = LLMClient(config, client=fake).chat(MENSAJES)
    assert fake.completions.llamadas == 3
    assert resultado["text"]


def test_tras_agotar_los_reintentos_lanza_llmcallerror(config):
    """``max_retries`` reintentos => ``max_retries + 1`` intentos, y luego falla.

    El runner debe registrar esto como ``status="error"``, nunca como ataque
    fallido: un timeout no es evidencia de que la defensa funcionó.
    """
    fake = FakeClient(fallos=99)
    with pytest.raises(LLMCallError):
        LLMClient(config, client=fake).chat(MENSAJES)
    assert fake.completions.llamadas == config.rate_limit.max_retries + 1


def test_un_429_se_reintenta(config):
    """El rate limit del proveedor es transitorio: hay que reintentarlo."""
    respuesta_http = httpx2.Response(
        429, request=httpx2.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    )
    fake = FakeClient(
        fallos=1,
        error=RateLimitError("demasiadas peticiones", response=respuesta_http, body=None),
    )
    LLMClient(config, client=fake).chat(MENSAJES)
    assert fake.completions.llamadas == 2


def test_un_error_no_recuperable_no_se_reintenta(config):
    """Un 401 no mejora reintentando: hay que fallar de inmediato."""
    respuesta_http = httpx2.Response(
        401, request=httpx2.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    )
    fake = FakeClient(
        fallos=99,
        error=APIStatusError("clave inválida", response=respuesta_http, body=None),
    )
    with pytest.raises(LLMCallError, match="401"):
        LLMClient(config, client=fake).chat(MENSAJES)
    assert fake.completions.llamadas == 1


@pytest.mark.parametrize("malos", [[], "hola", [{"role": "user"}], [{"content": "x"}]])
def test_rechaza_mensajes_malformados_antes_de_gastar_una_llamada(config, malos):
    """Validar antes de llamar evita quemar cuota en una petición inválida."""
    fake = FakeClient()
    with pytest.raises(ValueError):
        LLMClient(config, client=fake).chat(malos)
    assert fake.completions.llamadas == 0
