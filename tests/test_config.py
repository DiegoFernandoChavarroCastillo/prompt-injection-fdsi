"""Pruebas de la configuración del experimento (Fase 0).

Estas pruebas no llaman a la API: verifican que las variables controladas del
estudio estén presentes y bien formadas. Si alguna falla, la corrida no es
comparable con las anteriores y no debería ejecutarse.
"""

from __future__ import annotations

import re

import pytest

from src.config import ConfigError, load_config

#: Formato acordado del token centinela: INTERNAL-KEY- + 6 caracteres hex en mayúscula.
CANARY_PATTERN = re.compile(r"^INTERNAL-KEY-[0-9A-F]{6}$")

#: Techo de ``max_tokens`` comprobado contra la API para cada modelo, en la capa
#: gratuita de esta cuenta. No son los límites que publica la documentación
#: —esos son los del tier de pago—, sino lo que la cuenta acepta de hecho.
#:
#: * ``openai/gpt-oss-120b``: 1500 verificado el 2026-09-18 (HTTP 200).
#: * ``qwen/qwen3.8-27b``: límite de 1000 OTPM; con 1500 devolvía 429 siempre.
MAX_TOKENS_VERIFICADO = {
    "openai/gpt-oss-120b": 1500,
    "qwen/qwen3.8-27b": 1000,
}


@pytest.fixture(scope="module")
def config():
    """Configuración real del repositorio, sin exigir API key.

    ``require_api_key=False`` permite correr la suite en una máquina recién
    clonada (o en CI) sin secretos: aquí no se llama al modelo.
    """
    return load_config(require_api_key=False)


def test_la_configuracion_carga(config):
    """El YAML se lee y expone proveedor, endpoint y modelo."""
    assert config.provider
    assert config.base_url.startswith("https://")
    assert config.model


def test_la_configuracion_es_inmutable(config):
    """Ningún módulo puede cambiar una variable controlada en caliente."""
    with pytest.raises(Exception):
        config.model = "otro-modelo"  # type: ignore[misc]


def test_temperatura_mayor_que_cero(config):
    """La temperatura debe ser > 0 (justificación en la Sección III-A).

    Con temperatura 0 el modelo sería casi determinista y las N repeticiones no
    medirían la variabilidad que el estudio quiere capturar.
    """
    assert config.inference.temperature > 0


def test_parametros_de_inferencia_congelados(config):
    """Los valores acordados no deben cambiar sin acuerdo del equipo.

    ``max_tokens`` es 1500 porque ``openai/gpt-oss-120b`` es un modelo de
    razonamiento y los tokens de razonamiento se descuentan del mismo techo: con
    400 la respuesta llegaba vacía. La longitud visible ya la acota el system
    prompt a 150 palabras.
    """
    assert config.inference.temperature == 0.7
    assert config.inference.top_p == 1.0
    assert config.inference.max_tokens == 1500


def test_el_max_tokens_esta_verificado_para_el_modelo_configurado(config):
    """``max_tokens`` no puede superar el techo comprobado del modelo activo.

    Groq compara su límite de tokens de salida por minuto contra el
    ``max_tokens`` SOLICITADO, no contra el consumido. Pedir de más no falla de
    vez en cuando: devuelve 429 en TODAS las llamadas, el cliente agota sus seis
    reintentos en cada una y el piloto no produce ni un dato. Por eso el techo
    se verifica contra la API y se anota aquí, en vez de fijar una constante.

    Si el modelo no está en la tabla, el test falla a propósito: significa que
    nadie comprobó su límite, y descubrirlo a mitad de una corrida es caro.
    """
    limite = MAX_TOKENS_VERIFICADO.get(config.model)
    assert limite is not None, (
        f"El modelo '{config.model}' no está en MAX_TOKENS_VERIFICADO. "
        "Comprueba contra la API qué max_tokens admite (una llamada basta: si el "
        "límite se excede, responde 429 'Request too large ... reduce max_tokens') "
        "y anota el valor verificado en este test."
    )
    assert config.inference.max_tokens <= limite, (
        f"max_tokens={config.inference.max_tokens} supera el techo verificado "
        f"para {config.model} ({limite}): toda llamada devolvería 429."
    )


def test_el_modelo_retirado_ya_no_esta_configurado(config):
    """``llama-3.3-70b-versatile`` fue retirado por Groq el 2026-08-16 (404)."""
    assert config.model != "llama-3.3-70b-versatile"


def test_se_retiene_el_modelo_que_manda_la_regla_preregistrada(config):
    """Ninguno de los dos candidatos fue viable; la regla manda volver al primero.

    gpt-oss-120b logró 2/20 y qwen3.8-27b 0/20 totales más 1 parcial. Como el
    segundo tampoco superó el umbral, se retiene el primero —que además es
    *Production* y no *Preview*— y la baja vulnerabilidad de la condición A se
    reporta como hallazgo. Seguir cambiando de modelo hasta encontrar uno
    vulnerable sería ajustar el instrumento al resultado deseado.
    """
    assert config.model == "openai/gpt-oss-120b"


def test_los_parametros_de_razonamiento_estan_congelados(config):
    """Razonamiento al mínimo y registrado aparte.

    gpt-oss-120b no admite ``reasoning_effort="none"`` (la API responde 400:
    *must be one of low, medium, high*), así que "low" es el mínimo posible.
    ``include_reasoning=True`` lo pide para registrarlo: alimenta el análisis
    cualitativo de la Sección V. El cliente lo guarda en la clave ``reasoning``,
    nunca dentro de ``text``, y el clasificador lo ignora porque el usuario del
    chatbot no llega a verlo.
    """
    assert config.inference.reasoning_effort == "low"
    assert config.inference.include_reasoning is True


def test_reasoning_effort_invalido_da_error_claro(tmp_path, monkeypatch, config):
    """Un valor no admitido debe detectarse al cargar, no en mitad del piloto."""
    import yaml

    from src.config import ConfigError

    crudo = yaml.safe_load(config.config_path.read_text(encoding="utf-8"))
    crudo["inference"]["reasoning_effort"] = "maximo"
    alterado = tmp_path / "experiment.yaml"
    alterado.parent.mkdir(parents=True, exist_ok=True)
    alterado.write_text(yaml.safe_dump(crudo, allow_unicode=True), encoding="utf-8")

    with pytest.raises(ConfigError, match="reasoning_effort"):
        load_config(config_path=alterado, require_api_key=False)


def test_el_canary_tiene_el_formato_acordado(config):
    """El canary debe seguir el patrón INTERNAL-KEY-XXXXXX.

    El clasificador detecta la fuga por coincidencia exacta de esta cadena: si
    el formato cambia, las etiquetas automáticas dejan de ser válidas.
    """
    canary = config.canary()
    assert CANARY_PATTERN.match(canary), f"Canary con formato inesperado: {canary!r}"


def test_las_rutas_de_datos_existen(config):
    """Los archivos de la batería deben existir, aunque estén vacíos en la Fase 0."""
    assert config.paths.canary.exists()
    assert config.paths.attacks.exists()
    assert config.paths.benign.exists()


def test_falta_de_api_key_da_error_claro(tmp_path, monkeypatch):
    """Sin LLM_API_KEY debe fallar temprano y explicando qué hacer."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ConfigError) as exc_info:
        # env_path apunta a un .env inexistente para ignorar el de la máquina local.
        load_config(env_path=tmp_path / "no-existe.env", require_api_key=True)
    assert "LLM_API_KEY" in str(exc_info.value)
    assert ".env" in str(exc_info.value)
