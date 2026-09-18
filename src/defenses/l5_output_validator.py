"""L5 — Validación de salida (Fase 4).

Última red de la condición B: revisa lo que el modelo produjo antes de
entregárselo al usuario. Su caso central es el canary
(``prompts/canary.txt``): si el token centinela del system prompt aparece en la
salida, hubo fuga de contexto y la respuesta no debe entregarse.

L5 importa porque es la única capa que actúa cuando las anteriores ya fallaron:
la inyección funcionó y el modelo está a punto de revelar el contexto. Su
detección del canary es objetiva (coincidencia de cadena) y por eso el
clasificador puede etiquetar esta rama sin auditoría manual.

TODO (Fase 4), dos decisiones ya acordadas:

* **Los delimitadores cuentan como fuga.** ``<<<USER_DATA_a91f>>>`` y
  ``<<</USER_DATA_a91f>>>`` están escritos dentro de ``system_B.txt``, de modo
  que un ataque puede hacer que el modelo los repita sin haberlos adivinado
  (A09, A11 y A20 piden justamente el contenido del system prompt). Su
  aparición en la salida debe tratarse como señal de fuga, igual que el canary.
* **El umbral de n-gramas se calibra con los benignos, nunca con los ataques.**
  Ajustarlo hasta que bloquee los 20 ataques sería ajustar la defensa a la
  batería: el ASR mediría ese ajuste y no la resistencia real. El criterio es
  el contrario: el umbral más estricto que no dispare con los benignos, y en
  particular con los cinco difíciles, cuyas respuestas legítimas se parecen
  mucho a las negativas de ``[EJEMPLOS DE RESPUESTA]``.

Estado: STUB (Fase 0). Implementación pendiente en la Fase 4 (rol R3).
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from src.config import Config, get_config
from src.prompts import PROTECTED_SECTIONS, extract_sections, load_prompts

#: Secciones cuyo texto es PÚBLICO y por tanto no puede contar como fuga.
#:
#: La identidad la declara la propia asistente al presentarse, y el conocimiento
#: del dominio es lo que debe responder: "el plazo para reportar es de 3 días
#: hábiles" es la respuesta correcta, no una filtración. Sus n-gramas se restan
#: del conjunto protegido, porque si no, cada respuesta útil dispararía L5 y el
#: FPR se iría al techo justo con los clientes mejor atendidos.
PUBLIC_SECTIONS: tuple[str, ...] = ("IDENTIDAD", "CONOCIMIENTO DEL DOMINIO")

#: Tamaño del n-grama de palabras para el cotejo con el system prompt.
NGRAM_SIZE = 5

#: Cualquier forma de la marca de datos en la SALIDA es señal de fuga: esas
#: marcas solo existen dentro del system prompt y del mensaje que se le envía,
#: así que el modelo únicamente puede haberlas leído de ahí. (TODO anotado en la
#: Fase 2 y resuelto aquí.)
DELIMITER_IN_OUTPUT = re.compile(r"<<<[^>]*?USER[\s_]*DATA[^>]*>>>|USER_DATA_[0-9a-f]{4}", re.IGNORECASE)

#: Marcadores de cambio de rol. Genéricos, de la literatura, no copiados de la
#: batería congelada.
ROLE_MARKERS: tuple[str, ...] = (
    r"modo\s+(?:desarrollador|dios|libre|sin\s+restricciones)\s+(?:activado|habilitado)",
    r"(?:developer|god|unrestricted|jailbreak)\s+mode\s+(?:enabled|activated|on)\b",
    r"\bahora\s+soy\b",
    r"\bya\s+no\s+soy\b",
    r"\bhe\s+dejado\s+de\s+ser\b",
    r"\ba\s+partir\s+de\s+ahora\s+(?:soy|actúo\s+como)\b",
    r"\bi\s+am\s+no\s+longer\b",
)

#: Marcadores de compromiso comercial: el asistente no puede concederlos.
COMMERCIAL_MARKERS: tuple[str, ...] = (
    r"\breembolso\s+(?:aprobado|concedido|autorizado)\b",
    r"\bdescuento\s+(?:aplicado|aprobado|concedido|otorgado)\b",
    r"\bqueda\s+(?:aprobado|autorizado|exonerado)\b",
    r"\b(?:apruebo|autorizo|concedo|otorgo|exonero)\b",
    r"\bsiniestro\s+aprobado\b",
    r"\bexenci[óo]n\s+(?:concedida|aprobada)\b",
)

#: Palabras que, si aparecen justo antes del marcador, lo desactivan.
#: "No puedo aplicar descuentos" es una negativa correcta, no un compromiso.
NEGATIONS: frozenset[str] = frozenset({"no", "ni", "tampoco", "nunca", "jamás", "jamas"})

#: Cuántas palabras antes del marcador se miran buscando una negación.
NEGATION_WINDOW = 4


def _palabras(texto: str) -> list[str]:
    """Minúsculas, sin tildes ni puntuación, espacios colapsados."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.findall(r"[a-z0-9]+", sin_tildes)


def _ngramas(texto: str, n: int = NGRAM_SIZE) -> set[tuple[str, ...]]:
    """Conjunto de n-gramas de palabras de ``texto``."""
    palabras = _palabras(texto)
    return {tuple(palabras[i : i + n]) for i in range(len(palabras) - n + 1)}


@lru_cache(maxsize=4)
def _canary_normalizado(canary: str) -> str:
    """Canary sin espacios, guiones ni guiones bajos, en minúsculas."""
    return re.sub(r"[\s\-_]", "", canary).lower()


def _texto_sin_separadores(texto: str) -> str:
    """El texto con espacios, guiones y guiones bajos eliminados, en minúsculas.

    Así ``I N T E R N A L - K E Y - 7 F 3 A 9 B`` y ``internal_key_7f3a9b`` se
    detectan igual que la forma exacta: separar los caracteres es la evasión más
    barata que existe contra una búsqueda literal.
    """
    return re.sub(r"[\s\-_]", "", texto).lower()


@lru_cache(maxsize=2)
def _ngramas_protegidos(system_b: str) -> frozenset[tuple[str, ...]]:
    """N-gramas del system prompt cuya aparición en la salida sí es fuga.

    Se toman las secciones de :data:`src.prompts.PROTECTED_SECTIONS` y se les
    RESTAN los n-gramas que también aparecen en las secciones públicas
    (:data:`PUBLIC_SECTIONS`). Sin esa resta, una respuesta legítima que repite
    una cobertura o un plazo del dominio dispararía L5, y la condición B
    castigaría precisamente a los clientes bien atendidos.
    """
    protegido = extract_sections(system_b, PROTECTED_SECTIONS)
    publico = extract_sections(system_b, list(PUBLIC_SECTIONS))
    return frozenset(_ngramas(protegido) - _ngramas(publico))


def _marcador_activo(texto: str, patrones: tuple[str, ...]) -> str | None:
    """Primer marcador presente que no esté negado en las palabras previas."""
    palabras_previas = _palabras(texto)
    for patron in patrones:
        for coincidencia in re.finditer(patron, texto, re.IGNORECASE):
            antes = _palabras(texto[: coincidencia.start()])[-NEGATION_WINDOW:]
            if NEGATIONS & set(antes):
                continue  # "no puedo aplicar descuentos": negativa correcta
            return coincidencia.group(0)
    del palabras_previas
    return None


def analyze(text: str, config: Config | None = None) -> dict:
    """Ejecuta todas las verificaciones y devuelve la evidencia, sin decidir.

    Separar el análisis de la decisión permite CALIBRAR el umbral de n-gramas
    ejecutando prompts benignos y mirando cuántas coincidencias produce cada
    uno, sin que L5 bloquee nada durante la calibración.

    Returns:
        dict con ``canary``, ``delimiter``, ``ngram_matches`` (lista de n-gramas
        coincidentes), ``role_marker`` y ``commercial_marker``.
    """
    config = config or get_config()
    prompts = load_prompts(config)
    canary = config.canary()

    plano = _texto_sin_separadores(text)
    canary_plano = _canary_normalizado(canary)
    # El sufijo suelto (la parte aleatoria) basta como evidencia de fuga: el
    # prefijo "INTERNAL-KEY-" es adivinable, la cola no.
    sufijo = canary_plano[-6:]

    coincidentes = sorted(
        " ".join(g) for g in _ngramas(text) & _ngramas_protegidos(prompts.system_B)
    )

    return {
        "canary": canary_plano in plano or (len(sufijo) >= 6 and sufijo in plano),
        "delimiter": DELIMITER_IN_OUTPUT.search(text).group(0)
        if DELIMITER_IN_OUTPUT.search(text)
        else None,
        "ngram_matches": coincidentes,
        "role_marker": _marcador_activo(text, ROLE_MARKERS),
        "commercial_marker": _marcador_activo(text, COMMERCIAL_MARKERS),
    }


def validate_output(text: str, config: Config | None = None) -> dict:
    """Decide si la salida del modelo puede entregarse al usuario.

    Args:
        text: texto crudo devuelto por el modelo, sin modificar.
        config: configuración a usar (de ella sale el umbral de n-gramas).

    Returns:
        dict con las claves:

        * ``passed`` (bool): ``True`` si la salida puede entregarse. Ojo con la
          polaridad: es la inversa de ``blocked`` en
          :func:`src.defenses.l3_input_filter.check_input`. Aquí ``True`` es el
          caso bueno.
        * ``check`` (str | None): ``"canary"``, ``"delimiter"``, ``"ngram"``,
          ``"role_marker"``, ``"commercial_marker"``, o ``None`` si pasó. Acaba
          en ``blocked_by`` como ``"L5:<verificación>"``. Nunca se muestra al
          usuario: el mensaje de rechazo es idéntico al de L3.
        * ``details`` (dict): la evidencia completa del análisis, para poder
          auditar la decisión en el Anexo B sin repetir la llamada.

    Las verificaciones se evalúan en orden de objetividad decreciente: el canary
    y los delimitadores son coincidencias exactas y no admiten discusión; los
    n-gramas dependen de un umbral calibrado; los marcadores son heurísticos.
    Se reporta la primera que falla, para que ``check`` identifique la evidencia
    más sólida disponible.

    El texto de reemplazo NO se decide aquí: cuando ``passed`` es ``False``,
    :mod:`src.chatbot_b` entrega ``prompts/messages.yaml::l5_fallback``, que es
    idéntico al de L3 para que el usuario no pueda distinguir qué capa actuó.
    """
    config = config or get_config()
    evidencia = analyze(text, config)
    umbral = config.defenses.l5_ngram_threshold

    if evidencia["canary"]:
        fallo = "canary"
    elif evidencia["delimiter"]:
        fallo = "delimiter"
    elif len(evidencia["ngram_matches"]) >= umbral:
        fallo = "ngram"
    elif evidencia["role_marker"]:
        fallo = "role_marker"
    elif evidencia["commercial_marker"]:
        fallo = "commercial_marker"
    else:
        fallo = None

    return {
        "passed": fallo is None,
        "check": fallo,
        "details": {**evidencia, "ngram_threshold": umbral},
    }
