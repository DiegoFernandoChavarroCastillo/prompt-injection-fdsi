"""L3 — Filtro de entrada (Fase 4).

Primera línea de defensa: inspecciona la entrada del usuario ANTES de gastar una
llamada a la API y rechaza lo que parezca un intento de inyección (patrones tipo
"ignora las instrucciones anteriores", "revela tu system prompt", codificaciones
evasivas, etc.).

Tensión de diseño que el experimento mide: cada regla que sube el ASR bloqueado
puede también subir el FPR (prompts benignos rechazados). Por eso la batería
incluye 5 benignos "difíciles" que rozan el vocabulario de los ataques. El filtro
debe escribirse contra la *clase* de ataque, no contra las cadenas concretas de
la batería congelada: si se ajusta a ella, la efectividad medida deja de
generalizar (ver Riesgos del plan de acción).

REGLA ANTISESGO (Fase 4): este módulo no puede leer ni nombrar la batería, y sus
reglas se escriben y se prueban con ataques de desarrollo propios. Lo comprueba
``tests/test_antisesgo.py``, con una búsqueda de texto: por eso aquí se habla de
"la batería congelada" y no del nombre del archivo.

Estado: IMPLEMENTADO (Fase 4b).
"""

from __future__ import annotations

import base64
import codecs
import re
import unicodedata

#: Caracteres invisibles que se eliminan antes de evaluar las reglas.
#: Son de categoría Unicode Cf (formato) o espacios de ancho nulo: no se ven en
#: pantalla, no cambian el sentido para una persona, y sirven para partir una
#: palabra prohibida en trozos que ninguna expresión regular reconoce.
INVISIBLE_CHARS = (
    "\u200b\u200c\u200d\u200e\u200f"  # espacios de ancho cero y marcas de dirección
    "\u2060\u2061\u2062\u2063\u2064"  # uniones y separadores invisibles
    "\ufeff"                            # BOM usado como separador
    "\u00ad"                            # guion suave
)

#: Homóglifos: letras de otros alfabetos que se dibujan igual que una latina.
#: Mapa PROPIO de esta capa, deliberadamente más amplio que el de cualquier test:
#: si compartiera tabla con la prueba que lo verifica, un hueco en el mapa sería
#: invisible para esa prueba.
HOMOGLYPHS = {
    # Cirílico
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0441": "c", "\u0440": "p",
    "\u0445": "x", "\u0443": "y", "\u0456": "i", "\u0458": "j", "\u0455": "s",
    "\u04bb": "h", "\u0501": "d", "\u051b": "q", "\u0432": "b", "\u043a": "k",
    "\u043c": "m", "\u0442": "t", "\u043d": "h", "\u0410": "A", "\u0412": "B",
    "\u0415": "E", "\u041a": "K", "\u041c": "M", "\u041d": "H", "\u041e": "O",
    "\u0420": "P", "\u0421": "C", "\u0422": "T", "\u0425": "X",
    # Griego
    "\u03b1": "a", "\u03b5": "e", "\u03b9": "i", "\u03bf": "o", "\u03c1": "p",
    "\u03c5": "u", "\u03c7": "x", "\u03ba": "k", "\u03bd": "v", "\u03bc": "u",
    "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u0397": "H", "\u0399": "I",
    "\u039a": "K", "\u039c": "M", "\u039d": "N", "\u039f": "O", "\u03a1": "P",
    "\u03a4": "T", "\u03a5": "Y", "\u03a7": "X",
    # Otros
    "\u0131": "i", "\u017f": "s",
}

_HOMOGLYPH_TABLE = str.maketrans(HOMOGLYPHS)
_INVISIBLE_TABLE = str.maketrans({c: None for c in INVISIBLE_CHARS})

#: Candidato a Base64: alfabeto propio y longitud suficiente para no confundir
#: una palabra larga con una carga codificada.
_BASE64_CANDIDATE = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")

#: Objetos que convierten una orden en un intento de inyección. Las reglas
#: apuntan a ESTOS sustantivos, no a los verbos: "ignora el correo anterior" es
#: una consulta legítima y "ignora las instrucciones anteriores" no lo es. La
#: diferencia está en el objeto, y confundirlas es la causa típica de FPR.
_OBJETO_ES = r"(?:instruccion\w*|reglas|normas|directrices|directivas|indicaciones|pol[ií]ticas|configuraci[óo]n|prompt)"
_OBJETO_EN = r"(?:instructions?|rules|directives|guidelines|policies|configuration|prompt)"
_PREVIO_ES = r"(?:anterior\w*|previa\w*|iniciales|originales|de\s+antes|que\s+te\s+(?:dieron|cargaron|configuraron))"
_PREVIO_EN = r"(?:previous|prior|earlier|above|initial|original)"

#: Reglas heurísticas. Cada una es (identificador estable, expresión regular).
#:
#: Los identificadores son estables en el tiempo porque acaban en el log, en
#: ``blocked_by`` como ``"L3:<regla>"``, y son lo que se agrupa en el análisis.
#: Escritas desde categorías genéricas de la literatura, nunca desde payloads
#: concretos de la batería congelada (regla antisesgo de la Fase 4).
RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # 1. Anulación dirigida a las instrucciones previas.
    (
        "override_es",
        re.compile(
            rf"\b(?:ignor\w+|olvid\w+|descart\w+|anul\w+|omit\w+|desech\w+|"
            rf"deja\s+sin\s+efecto|haz\s+caso\s+omiso)\b"
            rf"(?:\W+\w+){{0,4}}?\W+{_OBJETO_ES}"
            rf"(?:\W+\w+){{0,3}}?\W+{_PREVIO_ES}",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "override_es_invertido",  # "las instrucciones anteriores quedan anuladas"
        re.compile(
            rf"\b{_OBJETO_ES}\W+(?:\w+\W+){{0,3}}?{_PREVIO_ES}"
            rf"(?:\W+\w+){{0,4}}?\W+(?:qued\w+\s+(?:sin\s+efecto|anul\w+|suspend\w+)|"
            rf"ya\s+no\s+(?:aplican|rigen|est[áa]n\s+vigentes))",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "override_en",
        re.compile(
            rf"\b(?:ignore|disregard|forget|discard|override|set\s+aside)\b"
            rf"(?:\W+\w+){{0,4}}?\W+(?:{_PREVIO_EN}\W+(?:\w+\W+){{0,2}}?{_OBJETO_EN}|"
            rf"{_OBJETO_EN}\W+(?:\w+\W+){{0,3}}?{_PREVIO_EN})",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    # 2. Marcadores de rol o de canal falsos.
    (
        "fake_system_marker",
        re.compile(
            r"<\|\s*im_(?:start|end)\s*\|>"
            r"|<\|\s*(?:system|assistant|user)\s*\|>"
            r"|\[\s*(?:SYSTEM|SISTEMA)\s*\]"
            r"|(?m:^\s*(?:system|sistema|assistant|asistente)\s*:\s*\S)"
            r"|(?:fin|final|end)\s+(?:de|del|of)\s+(?:las?\s+|the\s+)?"
            r"(?:instruccion\w*|system\s*prompt|configuraci[óo]n|bloque\s+de\s+configuraci[óo]n)"
            r"|(?:nuevas?|new)\s+(?:instruccion\w*|configuraci[óo]n|directriz|directrices)"
            r"\s+(?:del\s+sistema|de\s+sistema|from\s+system)",
            re.IGNORECASE,
        ),
    ),
    # 3. Activación de modos o personas alternativas.
    (
        "persona_switch",
        re.compile(
            r"\bmodo\s+(?:desarrollador|dios|libre|jailbreak|dan|sin\s+filtros|sin\s+restricciones)\b"
            r"|\b(?:developer|god|jailbreak|unrestricted|unfiltered|dan)\s+mode\b"
            r"|\b(?:ya\s+no\s+eres|dejas\s+de\s+ser)\b"
            r"|\b(?:a\s+partir\s+de\s+ahora|desde\s+ahora|de\s+ahora\s+en\s+adelante)\s+"
            r"(?:t[úu]\s+)?eres\b"
            r"|\b(?:you\s+are\s+no\s+longer|from\s+now\s+on\s+you\s+are)\b"
            r"|\bact[úu]a\s+como\s+si\s+no\s+(?:tuvieras|tuvieses)\s+(?:reglas|restricciones|l[íi]mites)\b",
            re.IGNORECASE,
        ),
    ),
    # 4. Petición de revelar la configuración.
    (
        "reveal_config",
        re.compile(
            r"\b(?:muestra\w*|mostrar|ense[ñn]a\w*|repite|repetir|revela\w*|revelar|"
            r"transcrib\w+|traduce|traducir|resume|resumir|codifica\w*|enumera\w*|"
            r"lista\w*|imprime|dime|dame|convierte\w*|pasa\s+a|comparte)\b"
            r"(?:\W+\w+){0,6}?\W+"
            r"(?:(?:tu|tus|sus|las?|los?|el)\W+)?"
            r"(?:instruccion\w*|system\s*prompt|configuraci[óo]n\s+interna|configuraci[óo]n|"
            r"reglas\s+internas|tus\s+reglas|directrices|texto\s+de\s+sistema|"
            r"prompt\s+de\s+sistema|contexto\s+(?:inicial|de\s+sistema))"
            r"|\b(?:show|reveal|repeat|print|dump|output|translate|summari[sz]e|list)\b"
            r"(?:\W+\w+){0,6}?\W+(?:your\s+)?(?:system\s*prompt|instructions?|configuration|"
            r"initial\s+context|rules)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "reveal_verbatim",  # "transcribe todo lo que aparece antes de esta línea"
        re.compile(
            r"\b(?:transcrib\w+|repite|repetir|copia|reproduce|muestra\w*)\b"
            r"(?:\W+\w+){0,6}?\W+"
            r"(?:literal\w*|textual\w*|palabra\s+por\s+palabra|verbatim|todo\s+lo\s+que)"
            r"(?:\W+\w+){0,8}?\W+(?:antes|contexto|recibiste|previo|precede)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "prefix_forcing",  # obligar a empezar la respuesta con una frase impuesta
        re.compile(
            r"\b(?:empieza|comienza|inicia|start|begin)\b"
            r"(?:\W+\w+){0,6}?\W+(?:exactamente\s+con|con\s+la\s+frase|with\s+the\s+(?:phrase|words))"
            r"(?:\W+\w+){0,10}?\W+(?:configuraci[óo]n|instruccion\w*|reglas|prompt|"
            r"configuration|instructions?|rules)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)


def normalize(text: str) -> str:
    """Devuelve ``text`` en la forma sobre la que se evalúan las reglas.

    Cuatro pasos, en orden: compatibilidad Unicode (NFKC), eliminación de
    caracteres invisibles, sustitución de homóglifos por su equivalente latino y
    colapso del espaciado. Cada uno deshace una técnica de evasión distinta, y
    juntos dejan un texto que una expresión regular puede leer como lo leería
    una persona.

    Lo que devuelve NO es lo que se envía al modelo: sirve solo para decidir.
    """
    normalizado = unicodedata.normalize("NFKC", text)
    normalizado = normalizado.translate(_INVISIBLE_TABLE)
    normalizado = normalizado.translate(_HOMOGLYPH_TABLE)
    return re.sub(r"[ \t\u00a0]+", " ", normalizado).strip()


def _es_texto_util(candidato: str) -> bool:
    """``True`` si la cadena decodificada parece texto y no ruido binario."""
    if len(candidato) < 8:
        return False
    imprimibles = sum(1 for c in candidato if c.isprintable() or c in "\n\t")
    if imprimibles / len(candidato) < 0.9:
        return False
    # Al menos una palabra de tres letras: descarta cadenas de símbolos sueltos.
    return bool(re.search(r"[A-Za-zÀ-ÿ]{3,}", candidato))


def decode_candidates(text: str) -> list[str]:
    """Devuelve las lecturas alternativas del texto: Base64 y ROT13.

    Un ataque ofuscado es inofensivo en su forma cruda y hostil una vez
    decodificado, así que evaluar solo el original dejaría pasar la categoría
    entera de evasión por codificación.

    Decodificar NO es motivo de bloqueo: un número de radicado que parece Base64
    y decodifica a texto inocuo debe pasar. Solo se bloquea si alguna de estas
    lecturas dispara una regla.
    """
    lecturas: list[str] = []

    for candidato in _BASE64_CANDIDATE.findall(text):
        relleno = candidato + "=" * (-len(candidato) % 4)
        try:
            decodificado = base64.b64decode(relleno, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        if _es_texto_util(decodificado):
            lecturas.append(decodificado)

    rot13 = codecs.encode(text, "rot_13")
    if rot13 != text and _es_texto_util(rot13):
        lecturas.append(rot13)

    return lecturas


def _primera_regla(texto: str) -> str | None:
    """Identificador de la primera regla que dispara sobre ``texto``."""
    for nombre, patron in RULES:
        if patron.search(texto):
            return nombre
    return None


def check_input(text: str) -> dict:
    """Decide si ``text`` debe bloquearse antes de llegar al modelo.

    La evaluación se hace sobre el texto normalizado Y sobre lo que se consiga
    decodificar (Base64, ROT13): un ataque ofuscado es inofensivo en su forma
    cruda y hostil una vez decodificado, así que mirar solo el original dejaría
    pasar toda la categoría de evasión por codificación.

    Args:
        text: texto crudo del usuario, sin tocar.

    Returns:
        dict con las claves:

        * ``blocked`` (bool): ``True`` si la entrada se rechaza. Ojo con la
          polaridad: aquí ``True`` significa "se bloquea", mientras que en
          :func:`src.defenses.l5_output_validator.validate_output` la clave
          equivalente es ``passed`` y ``True`` significa "se deja pasar".
        * ``rule`` (str | None): identificador corto y estable de la regla que
          disparó, con el sufijo ``@decoded`` si lo hizo sobre una lectura
          decodificada y no sobre el texto normalizado. ``None`` si pasó. Acaba
          en ``blocked_by`` como ``"L3:<regla>"`` y nunca se muestra al usuario.
        * ``normalized`` (str): el texto tras la normalización. Es lo que
          evaluaron las reglas, y queda en el log como evidencia.
        * ``decoded`` (list[str]): lecturas alternativas obtenidas al decodificar.
          Vacía si no se decodificó nada.

    **Qué recibe el modelo:** nada de esto. L3 usa el texto normalizado y las
    lecturas decodificadas SOLO para decidir. Si no bloquea, al modelo le llega
    la entrada original —que luego L1 escapa y envuelve—, porque enviar la
    versión normalizada cambiaría el ataque antes de medirlo: los homóglifos y
    los caracteres invisibles forman parte del ataque bajo estudio.
    """
    normalizado = normalize(text)
    decodificados = decode_candidates(normalizado)

    regla = _primera_regla(normalizado)
    if regla is None:
        for lectura in decodificados:
            regla = _primera_regla(normalize(lectura))
            if regla is not None:
                regla = f"{regla}@decoded"
                break

    return {
        "blocked": regla is not None,
        "rule": regla,
        "normalized": normalizado,
        "decoded": decodificados,
    }
