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

    ``max_tokens`` subió de 400 a 1500 en la migración a ``openai/gpt-oss-120b``
    (2026-09-18): es un modelo de razonamiento y los tokens de razonamiento se
    descuentan de ese mismo techo, así que con 400 la respuesta llegaba vacía.
    """
    assert config.inference.temperature == 0.7
    assert config.inference.top_p == 1.0
    assert config.inference.max_tokens == 1500


def test_el_modelo_retirado_ya_no_esta_configurado(config):
    """llama-3.3-70b-versatile fue retirado por Groq el 2026-08-16.

    Devuelve HTTP 404 model_not_found: cualquier corrida con él falla entera.
    """
    assert config.model != "llama-3.3-70b-versatile"
    assert config.model == "openai/gpt-oss-120b"


def test_los_parametros_de_razonamiento_estan_congelados(config):
    """Razonamiento al mínimo y oculto en la respuesta.

    gpt-oss-120b no admite ``reasoning_effort="none"`` (la API responde 400:
    *must be one of low, medium, high*), así que "low" es el mínimo posible.
    ``include_reasoning=False`` evita que el razonamiento vuelva en la respuesta;
    si aun así volviera, el cliente lo guarda aparte y nunca dentro de ``text``.
    """
    assert config.inference.reasoning_effort == "low"
    assert config.inference.include_reasoning is False


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
