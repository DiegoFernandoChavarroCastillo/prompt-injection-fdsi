"""Carga de la batería de prueba: 20 ataques + 20 prompts benignos (Fase 2).

La batería es el instrumento de medición del estudio, y su validez depende de
que esté **congelada antes** de implementar las defensas: si los ataques se
retocaran después de ver qué bloquea L3, el ASR mediría lo bien que se ajustó la
batería al filtro, no lo bien que el filtro resiste ataques. Por eso
``scripts/freeze_battery.py`` deja un manifiesto con los hashes SHA-256 y
``tests/test_battery.py`` falla si los archivos cambian sin regenerarlo.

Estructura de los datos:

* **Ataques** (``data/attacks_v1.json``), 4 por cada categoría C1–C5:
  C1 sobrescritura directa, C2 suplantación de rol, C3 extracción del system
  prompt, C4 inyección por contexto engañoso, C5 evasión por ofuscación.
  Los de C5 llevan ``decoded_intent``: la intención en claro de un payload
  ofuscado (Base64, ROT13, homóglifos), necesaria para poder publicarlos en el
  Anexo A y para que el auditor humano sepa qué estaba pidiendo el ataque.
* **Benignos** (``data/benign_v1.json``): 15 ``ordinary`` y 5 ``hard_benign``.
  Los difíciles llevan ``trigger_lexicon``: el término que comparten con los
  ataques ("ignora", "instrucciones", "administrador"...) y que un filtro
  ingenuo bloquearía. Son los que hacen visible el FPR.

Los payloads se entregan **verbatim**, sin normalizar: A20 contiene homóglifos
cirílicos y espacios de ancho cero intencionales, y normalizarlos aquí
desactivaría el ataque antes de que llegue a L3.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config import Config, ConfigError, get_config

#: Categorías de ataque (Tabla 3 del artículo). 4 ataques en cada una.
CATEGORIES: tuple[str, ...] = ("C1", "C2", "C3", "C4", "C5")

#: Objetivo del atacante, en la taxonomía del artículo.
OBJECTIVES: frozenset[str] = frozenset(
    {"goal_hijacking", "policy_bypass", "prompt_leaking"}
)

#: Políticas del asistente (P1–P5) que cada ataque intenta vulnerar.
POLICIES: frozenset[str] = frozenset({"P1", "P2", "P3", "P4", "P5"})

#: Tipos de prompt benigno. Los ``hard_benign`` comparten léxico con los ataques.
BENIGN_TYPES: frozenset[str] = frozenset({"ordinary", "hard_benign"})

_ATTACK_FIELDS = (
    "id",
    "category",
    "category_name",
    "technique",
    "objective",
    "target_policies",
    "payload",
    "success_criterion",
    "partial_criterion",
)
_BENIGN_FIELDS = ("id", "type", "payload", "expected_behavior")


@dataclass(frozen=True, slots=True)
class Attack:
    """Un ataque de inyección directa de la batería.

    Attributes:
        id: identificador estable ``A01``–``A20``. Es la clave con la que el
            ataque se cita en el log, en las tablas y en el Anexo A.
        category: ``C1``–``C5``.
        category_name: nombre legible de la categoría.
        technique: técnica concreta dentro de la categoría.
        objective: ``goal_hijacking``, ``policy_bypass`` o ``prompt_leaking``.
        target_policies: políticas (``P1``–``P5``) que el ataque intenta vulnerar.
        payload: texto que se envía al asistente, **verbatim**.
        decoded_intent: intención en claro, solo para los payloads ofuscados de
            C5; ``None`` en el resto.
        success_criterion: qué debe ocurrir para etiquetar ÉXITO TOTAL.
        partial_criterion: qué cuenta como cesión parcial.
    """

    id: str
    category: str
    category_name: str
    technique: str
    objective: str
    target_policies: tuple[str, ...]
    payload: str
    decoded_intent: str | None
    success_criterion: str
    partial_criterion: str

    @property
    def is_obfuscated(self) -> bool:
        """``True`` si el payload viaja codificado y trae su intención en claro."""
        return self.decoded_intent is not None


@dataclass(frozen=True, slots=True)
class BenignPrompt:
    """Una consulta legítima. Su rechazo cuenta como falso positivo.

    Attributes:
        id: identificador estable ``B01``–``B20``.
        type: ``ordinary`` (consulta corriente) o ``hard_benign`` (comparte
            léxico con los ataques).
        payload: texto que se envía al asistente, verbatim.
        expected_behavior: qué debería responder el asistente; es el criterio
            con el que se decide si la respuesta fue atendida o degradada.
        trigger_lexicon: términos que este benigno comparte con los ataques y
            que un filtro ingenuo bloquearía. Vacío en los ``ordinary``.
    """

    id: str
    type: str
    payload: str
    expected_behavior: str
    trigger_lexicon: tuple[str, ...] = ()

    @property
    def is_hard(self) -> bool:
        """``True`` si es uno de los cinco benignos difíciles."""
        return self.type == "hard_benign"


def _load_json_array(path: Path, what: str) -> list[dict[str, Any]]:
    """Lee un JSON que debe contener un array de objetos."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(
            f"No se pudo leer {what} en {path}: {exc}. "
            "Verifica la ruta correspondiente en config/experiment.yaml."
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} no es JSON válido: {exc}") from exc
    if not isinstance(data, list):
        raise ConfigError(f"{path} debe contener un array JSON en la raíz.")
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ConfigError(f"{path}: el elemento {i} no es un objeto JSON.")
    return data


def _require_fields(item: dict[str, Any], fields: tuple[str, ...], path: Path) -> None:
    """Valida que ``item`` traiga todos los campos obligatorios, no vacíos."""
    for field in fields:
        if field not in item:
            raise ConfigError(f"{path}: a {item.get('id', '?')} le falta el campo '{field}'.")
        if item[field] in (None, "", [], ()):
            raise ConfigError(f"{path}: {item.get('id', '?')} tiene '{field}' vacío.")


def load_attacks(config: Config | None = None) -> tuple[Attack, ...]:
    """Lee la batería de ataques declarada en ``config/experiment.yaml``.

    Args:
        config: configuración a usar. Por defecto, la del repositorio.

    Returns:
        Los ataques en el orden del archivo. El orden de *ejecución* no es este:
        lo baraja el runner con ``execution_seed``.

    Raises:
        src.config.ConfigError: si el archivo falta, no es JSON válido o a algún
            ataque le falta un campo obligatorio.
    """
    config = config or get_config()
    path = config.paths.attacks
    items = _load_json_array(path, "la batería de ataques")

    attacks = []
    for item in items:
        _require_fields(item, _ATTACK_FIELDS, path)
        attacks.append(
            Attack(
                id=str(item["id"]),
                category=str(item["category"]),
                category_name=str(item["category_name"]),
                technique=str(item["technique"]),
                objective=str(item["objective"]),
                target_policies=tuple(item["target_policies"]),
                payload=item["payload"],
                decoded_intent=item.get("decoded_intent"),
                success_criterion=str(item["success_criterion"]),
                partial_criterion=str(item["partial_criterion"]),
            )
        )
    return tuple(attacks)


def load_benign(config: Config | None = None) -> tuple[BenignPrompt, ...]:
    """Lee el conjunto de prompts benignos declarado en ``config/experiment.yaml``.

    Args:
        config: configuración a usar. Por defecto, la del repositorio.

    Returns:
        Los prompts benignos en el orden del archivo.

    Raises:
        src.config.ConfigError: si el archivo falta, no es JSON válido o a algún
            prompt le falta un campo obligatorio.
    """
    config = config or get_config()
    path = config.paths.benign
    items = _load_json_array(path, "el conjunto de prompts benignos")

    prompts = []
    for item in items:
        _require_fields(item, _BENIGN_FIELDS, path)
        prompts.append(
            BenignPrompt(
                id=str(item["id"]),
                type=str(item["type"]),
                payload=item["payload"],
                expected_behavior=str(item["expected_behavior"]),
                trigger_lexicon=tuple(item.get("trigger_lexicon") or ()),
            )
        )
    return tuple(prompts)


# -- Preregistro: hashes y manifiesto ---------------------------------------
#
# El manifiesto es la evidencia de que la batería se congeló antes de escribir
# las defensas. Vive aquí, y no solo en el script, para que el test pueda
# verificarlo sin depender de scripts/.


def sha256_of(path: Path) -> str:
    """SHA-256 en hexadecimal del contenido **en bytes** de ``path``.

    Se hashean los bytes crudos, no el JSON parseado: así cualquier cambio queda
    registrado, incluido reordenar claves o reescribir los caracteres invisibles
    de A20 —justo lo que no debe pasar desapercibido.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_manifest(text: str) -> dict[str, str]:
    """Convierte el manifiesto en un diccionario ``clave: valor``.

    Ignora las líneas en blanco y las que empiezan por ``#``.
    """
    valores: dict[str, str] = {}
    for linea in text.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        clave, sep, valor = linea.partition(":")
        if sep:
            valores[clave.strip()] = valor.strip()
    return valores
