"""Carga de los prompts del experimento y extracción de secciones (Fase 1).

Un único punto de lectura para los cuatro artefactos de texto que definen las
dos condiciones:

* ``prompts/system_A.txt``   — condición A (baseline vulnerable).
* ``prompts/system_B.txt``   — condición B; empieza EXACTAMENTE con el contenido
  de ``system_A.txt`` y le añade los bloques de defensa. Esa simetría es lo que
  permite atribuir la diferencia de ASR a las capas y no a un cambio de tarea;
  la verifica ``tests/test_prompts.py``.
* ``prompts/l2_reminder.txt`` — recordatorio L2 que la condición B reinyecta
  DESPUÉS de la entrada del usuario ("defensa en sándwich"), para que la última
  instrucción del contexto sea del operador y no del atacante.
* ``prompts/messages.yaml``  — mensajes deterministas de rechazo de L3 y L5.

Los archivos se leen **verbatim**: ni se normalizan saltos de línea, ni se hace
``strip`` del contenido, ni se filtran comentarios. Lo que hay en el archivo es
literalmente lo que ve el modelo, y cualquier diferencia entre lo enviado y lo
publicado en el Anexo B invalidaría la evidencia.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.config import Config, ConfigError, get_config

#: Encabezado de sección: nombre entre corchetes, solo al inicio de línea.
_SECTION_HEADER_RE = re.compile(r"(?m)^\[(?P<name>[^\]\n]+)\][ \t]*$")

#: Secciones del system prompt contra las que L5 compara n-gramas (Fase 4).
#:
#: L5 detecta la fuga de contexto de dos formas: el canary (coincidencia exacta,
#: objetiva) y el solapamiento de n-gramas entre la salida del modelo y el
#: system prompt. Para lo segundo NO sirve comparar contra el prompt completo:
#:
#: * [CONOCIMIENTO DEL DOMINIO] se excluye porque una respuesta legítima lo
#:   reutiliza casi textualmente ("el plazo para reportar es de 3 días hábiles"
#:   es la respuesta correcta, no una fuga). Incluirlo dispararía el FPR.
#: * [EJEMPLOS DE RESPUESTA] se excluye porque una negativa correcta reproduce
#:   justamente esas frases: L5 bloquearía a la condición B por defenderse bien.
#: * [IDENTIDAD] y [CONFIGURACIÓN INTERNA] quedan fuera del cotejo por n-gramas:
#:   la identidad es pública (Aura se presenta) y el identificador interno ya
#:   está cubierto por la detección exacta del canary.
#:
#: Quedan, entonces, las secciones cuya aparición en la salida sí es evidencia
#: de que el modelo está revelando su configuración.
PROTECTED_SECTIONS: list[str] = [
    "POLÍTICAS",
    "SEGURIDAD — ENTRADA DEL USUARIO",
    "SEGURIDAD — CONFIDENCIALIDAD",
]


@dataclass(frozen=True, slots=True)
class Prompts:
    """Los prompts del experimento, tal cual están en disco.

    Inmutable por el mismo motivo que :class:`src.config.Config`: son variables
    controladas y ningún módulo debe poder reescribirlas en caliente.
    """

    system_A: str
    system_B: str
    l2_reminder: str
    l3_rejection: str
    l5_fallback: str


def _read(path: Path, what: str) -> str:
    """Lee un archivo de texto verbatim, o falla indicando cuál falta."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(
            f"No se pudo leer {what} en {path}: {exc}. "
            "Verifica la ruta correspondiente en config/experiment.yaml."
        ) from exc


def load_prompts(config: Config | None = None) -> Prompts:
    """Lee los prompts declarados en ``config/experiment.yaml``.

    Args:
        config: configuración a usar. Por defecto, la del repositorio.

    Returns:
        :class:`Prompts` con el contenido verbatim de cada archivo.

    Raises:
        src.config.ConfigError: si falta un archivo, ``messages.yaml`` no es un
            mapa YAML o le falta alguna de las dos claves de mensajes.
    """
    config = config or get_config()
    paths = config.paths

    raw_messages = _read(paths.messages, "los mensajes de rechazo")
    try:
        messages = yaml.safe_load(raw_messages)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{paths.messages} tiene un error de sintaxis YAML: {exc}") from exc
    if not isinstance(messages, dict):
        raise ConfigError(f"{paths.messages} debe contener un mapa YAML en la raíz.")

    faltantes = [clave for clave in ("l3_rejection", "l5_fallback") if not messages.get(clave)]
    if faltantes:
        raise ConfigError(
            f"Faltan las claves {faltantes} en {paths.messages}. "
            "L3 y L5 necesitan un mensaje de rechazo cada una."
        )

    return Prompts(
        system_A=_read(paths.system_A, "el system prompt de la condición A"),
        system_B=_read(paths.system_B, "el system prompt de la condición B"),
        l2_reminder=_read(paths.l2_reminder, "el recordatorio L2"),
        l3_rejection=str(messages["l3_rejection"]),
        l5_fallback=str(messages["l5_fallback"]),
    )


def extract_sections(text: str, names: list[str]) -> str:
    """Devuelve el contenido de las secciones ``names`` de ``text``.

    Una sección empieza en una línea que contiene únicamente su nombre entre
    corchetes (p. ej. ``[POLÍTICAS]``) y termina donde empieza el siguiente
    encabezado, o al final del texto. El encabezado en sí no se incluye en la
    salida: lo que interesa es el contenido a cotejar.

    Lo usa L5 (Fase 4) para acotar la comparación por n-gramas a
    :data:`PROTECTED_SECTIONS`.

    Args:
        text: system prompt completo.
        names: nombres de sección exactos, tal como aparecen entre corchetes
            (incluida la raya larga de ``SEGURIDAD — ENTRADA DEL USUARIO``).

    Returns:
        Las secciones pedidas concatenadas en el orden en que aparecen en el
        documento —no en el orden de ``names``—, separadas por una línea en
        blanco. Cadena vacía si ``names`` está vacío.

    Raises:
        ValueError: si alguna sección pedida no existe en ``text``. Es
            deliberado: si alguien renombra un encabezado, L5 dejaría de cotejar
            esa sección en silencio y la defensa se debilitaría sin que ningún
            test se diera cuenta. Mejor fallar ruidosamente.
    """
    if not names:
        return ""

    headers = list(_SECTION_HEADER_RE.finditer(text))
    wanted = set(names)
    seleccion: list[str] = []
    encontrados: set[str] = set()

    for i, header in enumerate(headers):
        name = header.group("name").strip()
        if name not in wanted:
            continue
        encontrados.add(name)
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        contenido = text[header.end() : end].strip()
        if contenido:
            seleccion.append(contenido)

    faltantes = [name for name in names if name not in encontrados]
    if faltantes:
        disponibles = [h.group("name").strip() for h in headers]
        raise ValueError(
            f"Secciones no encontradas en el prompt: {faltantes}. "
            f"Disponibles: {disponibles}. "
            "Si renombraste un encabezado, actualiza también PROTECTED_SECTIONS."
        )

    return "\n\n".join(seleccion)


def section_names(text: str) -> list[str]:
    """Lista los nombres de sección de ``text``, en orden de aparición.

    Auxiliar para los tests de simetría y para ``scripts/prompt_report.py``.
    """
    return [h.group("name").strip() for h in _SECTION_HEADER_RE.finditer(text)]
