"""Carga y validación de la configuración del experimento.

Fuentes de verdad, y sólo estas dos:

* ``config/experiment.yaml`` — variables controladas del experimento
  (proveedor, modelo, parámetros de inferencia, N, rate limit, rutas).
  Va versionado en git: es lo que hace reproducible el estudio.
* ``.env`` — secretos y overrides locales de máquina (``LLM_API_KEY``,
  opcionalmente ``LLM_BASE_URL``). NUNCA va a git.

La API key se obtiene exclusivamente del entorno cargado desde ``.env``
mediante ``python-dotenv``: no se acepta en el YAML ni escrita en el código,
para que ningún commit pueda contenerla.

Uso normal:

    from src.config import get_config

    cfg = get_config()
    print(cfg.model, cfg.inference.temperature)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

#: Raíz del repositorio (este archivo vive en ``<raíz>/src/config.py``).
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

#: Ubicaciones por defecto de los dos archivos de configuración.
DEFAULT_CONFIG_PATH: Path = PROJECT_ROOT / "config" / "experiment.yaml"
DEFAULT_ENV_PATH: Path = PROJECT_ROOT / ".env"

API_KEY_ENV_VAR = "LLM_API_KEY"
BASE_URL_ENV_VAR = "LLM_BASE_URL"


class ConfigError(RuntimeError):
    """Configuración ausente, incompleta o inválida.

    Se lanza con un mensaje accionable (qué falta y cómo arreglarlo) en vez de
    dejar que el error aparezca más tarde como un 401 de la API.
    """


@dataclass(frozen=True, slots=True)
class InferenceParams:
    """Parámetros de muestreo del modelo. CONGELADOS para todo el experimento."""

    temperature: float
    top_p: float
    max_tokens: int


@dataclass(frozen=True, slots=True)
class ExperimentParams:
    """Diseño experimental: repeticiones y semilla del orden de ejecución."""

    n_pilot: int
    n_final: int
    execution_seed: int


@dataclass(frozen=True, slots=True)
class RateLimitParams:
    """Política de cortesía y reintentos frente a la API del proveedor."""

    min_seconds_between_calls: float
    max_retries: int
    backoff_base_seconds: float


@dataclass(frozen=True, slots=True)
class Paths:
    """Rutas absolutas a los artefactos del experimento, resueltas desde la raíz.

    Todas las rutas se declaran en ``config/experiment.yaml`` y no se construyen
    a mano en ningún otro módulo: así un cambio de ubicación se hace en un solo
    sitio y los tests validan el conjunto completo.
    """

    canary: Path
    attacks: Path
    benign: Path
    system_A: Path
    system_B: Path
    l2_reminder: Path
    messages: Path


@dataclass(frozen=True, slots=True)
class Config:
    """Configuración completa e inmutable del experimento.

    Inmutable (``frozen=True``) a propósito: ningún módulo debe poder cambiar
    en caliente una variable controlada a mitad de una corrida.
    """

    provider: str
    base_url: str
    model: str
    inference: InferenceParams
    experiment: ExperimentParams
    rate_limit: RateLimitParams
    paths: Paths
    # repr=False para que la clave no aparezca en logs ni en trazas de error.
    api_key: str = field(repr=False)
    project_root: Path = PROJECT_ROOT
    config_path: Path = DEFAULT_CONFIG_PATH

    def canary(self) -> str:
        """Devuelve el canary (token centinela) sin espacios sobrantes."""
        try:
            return self.paths.canary.read_text(encoding="utf-8").strip()
        except OSError as exc:  # archivo borrado o ilegible
            raise ConfigError(
                f"No se pudo leer el canary en {self.paths.canary}: {exc}"
            ) from exc


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    """Obtiene ``key`` de ``mapping`` o falla indicando qué sección lo pide."""
    if key not in mapping:
        raise ConfigError(
            f"Falta la clave '{key}' en la sección '{where}' de experiment.yaml. "
            "Compara tu archivo con el del repositorio: las variables controladas "
            "deben estar todas presentes."
        )
    return mapping[key]


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    """Obtiene una sección del YAML validando que sea un mapa."""
    value = _require(raw, name, "raíz")
    if not isinstance(value, dict):
        raise ConfigError(
            f"La sección '{name}' de experiment.yaml debe ser un mapa de clave: valor."
        )
    return value


def _resolve(root: Path, value: Any) -> Path:
    """Convierte una ruta del YAML (relativa al repo) en ruta absoluta."""
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def load_config(
    config_path: Path | str | None = None,
    env_path: Path | str | None = None,
    require_api_key: bool = True,
) -> Config:
    """Lee ``experiment.yaml`` + ``.env`` y devuelve un :class:`Config` inmutable.

    Args:
        config_path: YAML alternativo (lo usan los tests). Por defecto,
            ``config/experiment.yaml``.
        env_path: archivo ``.env`` alternativo. Por defecto, ``.env`` en la raíz.
        require_api_key: si es ``True`` (normal), falla cuando no hay
            ``LLM_API_KEY``. Los tests que no llaman a la API lo ponen en
            ``False`` para poder validar el resto de la configuración.

    Raises:
        ConfigError: si falta el YAML, falta una clave, un valor es inválido o
            no hay API key habiendo sido exigida.
    """
    config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    env_path = Path(env_path) if env_path else DEFAULT_ENV_PATH
    root = config_path.resolve().parents[1] if config_path.is_absolute() else PROJECT_ROOT

    if not config_path.exists():
        raise ConfigError(
            f"No se encontró el archivo de configuración: {config_path}. "
            "Debe estar versionado en el repositorio (config/experiment.yaml)."
        )

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"experiment.yaml tiene un error de sintaxis YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path} debe contener un mapa YAML en la raíz.")

    # .env: secretos y overrides locales. No sobreescribe variables ya exportadas
    # en la shell, para permitir su uso en CI sin tocar archivos.
    load_dotenv(dotenv_path=env_path, override=False)

    inference_raw = _section(raw, "inference")
    experiment_raw = _section(raw, "experiment")
    rate_limit_raw = _section(raw, "rate_limit")
    paths_raw = _section(raw, "paths")

    try:
        inference = InferenceParams(
            temperature=float(_require(inference_raw, "temperature", "inference")),
            top_p=float(_require(inference_raw, "top_p", "inference")),
            max_tokens=int(_require(inference_raw, "max_tokens", "inference")),
        )
        experiment = ExperimentParams(
            n_pilot=int(_require(experiment_raw, "n_pilot", "experiment")),
            n_final=int(_require(experiment_raw, "n_final", "experiment")),
            execution_seed=int(_require(experiment_raw, "execution_seed", "experiment")),
        )
        rate_limit = RateLimitParams(
            min_seconds_between_calls=float(
                _require(rate_limit_raw, "min_seconds_between_calls", "rate_limit")
            ),
            max_retries=int(_require(rate_limit_raw, "max_retries", "rate_limit")),
            backoff_base_seconds=float(
                _require(rate_limit_raw, "backoff_base_seconds", "rate_limit")
            ),
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Valor numérico inválido en experiment.yaml: {exc}") from exc

    paths = Paths(
        canary=_resolve(root, _require(paths_raw, "canary", "paths")),
        attacks=_resolve(root, _require(paths_raw, "attacks", "paths")),
        benign=_resolve(root, _require(paths_raw, "benign", "paths")),
        system_A=_resolve(root, _require(paths_raw, "system_A", "paths")),
        system_B=_resolve(root, _require(paths_raw, "system_B", "paths")),
        l2_reminder=_resolve(root, _require(paths_raw, "l2_reminder", "paths")),
        messages=_resolve(root, _require(paths_raw, "messages", "paths")),
    )

    # El .env puede cambiar el endpoint sin tocar el YAML (plan B: Gemini).
    base_url = os.getenv(BASE_URL_ENV_VAR) or str(_require(raw, "base_url", "raíz"))

    api_key = (os.getenv(API_KEY_ENV_VAR) or "").strip()
    if require_api_key and not api_key:
        raise ConfigError(
            f"Falta {API_KEY_ENV_VAR}. Copia .env.example a .env "
            f"(cp .env.example .env) y escribe allí tu clave del proveedor. "
            f"El archivo .env está en .gitignore: nunca lo subas al repositorio."
        )

    return Config(
        provider=str(_require(raw, "provider", "raíz")),
        base_url=base_url,
        model=str(_require(raw, "model", "raíz")),
        inference=inference,
        experiment=experiment,
        rate_limit=rate_limit,
        paths=paths,
        api_key=api_key,
        project_root=root,
        config_path=config_path,
    )


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Configuración por defecto, cacheada (una sola lectura por proceso)."""
    return load_config()
