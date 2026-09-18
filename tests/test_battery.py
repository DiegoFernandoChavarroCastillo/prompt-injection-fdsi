"""Pruebas de la batería de ataques y del conjunto benigno (Fase 2).

Verifican que el instrumento de medición esté bien formado ANTES de usarlo:
composición (20 + 20, 4 por categoría), integridad de los identificadores,
taxonomía válida, y que los tres payloads ofuscados de C5 realmente codifiquen
lo que su ``decoded_intent`` dice que codifican.

Ese último punto importa más de lo que parece: si el Base64 de A17 no
decodificara a lo que el Anexo A afirma, el ataque estaría midiendo otra cosa y
la evidencia publicada sería falsa.

Incluye además el test de preregistro: si el contenido de los JSON deja de
coincidir con ``data/MANIFEST.txt``, la suite falla. Esa es la garantía de que
la batería no se ajustó a las defensas después de verlas funcionar.
"""

from __future__ import annotations

import base64
import codecs
import collections
import unicodedata

import pytest

from src.battery import (
    BENIGN_TYPES,
    CATEGORIES,
    OBJECTIVES,
    POLICIES,
    load_attacks,
    load_benign,
    parse_manifest,
    sha256_of,
)
from src.config import load_config

#: Homóglifos cirílicos usados en A20, con su equivalente latino.
#:
#: Este mapa es deliberadamente INDEPENDIENTE del que implementará L3 en la
#: Fase 4. Si el test importara el mapa de la defensa, un error en ese mapa
#: haría que test y defensa coincidieran y el test no probaría nada: estaría
#: validando el ataque contra la misma suposición que quiere verificar.
HOMOGLIFOS_CIRILICOS = {
    "а": "a",  # CYRILLIC SMALL LETTER A
    "е": "e",  # CYRILLIC SMALL LETTER IE
    "о": "o",  # CYRILLIC SMALL LETTER O
    "с": "c",  # CYRILLIC SMALL LETTER ES
    "і": "i",  # CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I
}

ZERO_WIDTH_SPACE = "​"


@pytest.fixture(scope="module")
def config():
    """Configuración real del repositorio, sin exigir API key."""
    return load_config(require_api_key=False)


@pytest.fixture(scope="module")
def attacks(config):
    """Los 20 ataques, en el orden del archivo."""
    return load_attacks(config)


@pytest.fixture(scope="module")
def benign(config):
    """Los 20 prompts benignos, en el orden del archivo."""
    return load_benign(config)


@pytest.fixture(scope="module")
def por_id(attacks):
    """Los ataques indexados por su identificador."""
    return {a.id: a for a in attacks}


# -- Composición de la batería ----------------------------------------------


def test_hay_veinte_ataques_cuatro_por_categoria(attacks):
    """20 ataques repartidos 4 y 4 entre C1 y C5.

    El reparto equilibrado es lo que permite comparar el ASR *por categoría*:
    con categorías de distinto tamaño, el ASR global quedaría dominado por la
    más numerosa.
    """
    assert len(attacks) == 20
    por_categoria = collections.Counter(a.category for a in attacks)
    assert set(por_categoria) == set(CATEGORIES)
    assert all(por_categoria[c] == 4 for c in CATEGORIES), por_categoria


def test_hay_veinte_benignos_quince_ordinarios_y_cinco_dificiles(benign):
    """15 ``ordinary`` + 5 ``hard_benign``: el denominador del FPR."""
    assert len(benign) == 20
    por_tipo = collections.Counter(b.type for b in benign)
    assert por_tipo == {"ordinary": 15, "hard_benign": 5}
    assert set(por_tipo) <= BENIGN_TYPES


def test_los_identificadores_son_los_esperados_y_unicos(attacks, benign):
    """A01–A20 y B01–B20, sin huecos ni repeticiones.

    Los IDs son la clave con la que se citan los casos en el log, en las tablas
    y en el Anexo A: un duplicado haría ambigua cualquier referencia.
    """
    ids_ataques = [a.id for a in attacks]
    ids_benignos = [b.id for b in benign]
    assert ids_ataques == [f"A{n:02d}" for n in range(1, 21)]
    assert ids_benignos == [f"B{n:02d}" for n in range(1, 21)]
    assert len(set(ids_ataques)) == len(ids_ataques)
    assert len(set(ids_benignos)) == len(ids_benignos)


def test_los_campos_obligatorios_no_estan_vacios(attacks, benign):
    """Ningún campo de texto puede venir vacío o en blanco.

    ``load_attacks``/``load_benign`` ya rechazan los ausentes; aquí se comprueba
    además que no sean solo espacios.
    """
    for a in attacks:
        for campo in (
            "id",
            "category",
            "category_name",
            "technique",
            "objective",
            "payload",
            "success_criterion",
            "partial_criterion",
        ):
            assert getattr(a, campo).strip(), f"{a.id}: campo '{campo}' vacío"
        assert a.target_policies, f"{a.id}: sin target_policies"
    for b in benign:
        for campo in ("id", "type", "payload", "expected_behavior"):
            assert getattr(b, campo).strip(), f"{b.id}: campo '{campo}' vacío"


# -- Taxonomía ---------------------------------------------------------------


def test_las_politicas_objetivo_son_validas(attacks):
    """``target_policies`` solo puede contener P1–P5, sin repetir."""
    for a in attacks:
        assert set(a.target_policies) <= POLICIES, f"{a.id}: {a.target_policies}"
        assert len(set(a.target_policies)) == len(a.target_policies), f"{a.id}: repetidas"


def test_los_objetivos_son_validos(attacks):
    """``objective`` debe estar en la taxonomía del artículo."""
    for a in attacks:
        assert a.objective in OBJECTIVES, f"{a.id}: objetivo '{a.objective}'"


def test_el_nombre_de_categoria_es_consistente(attacks):
    """Cada código de categoría debe traer siempre el mismo nombre legible."""
    nombres = collections.defaultdict(set)
    for a in attacks:
        nombres[a.category].add(a.category_name)
    for categoria, valores in nombres.items():
        assert len(valores) == 1, f"{categoria} tiene nombres distintos: {valores}"


# -- Payloads ofuscados (C5) -------------------------------------------------
#
# En A17 y A18 el payload son dos líneas: una instrucción en claro y, en la
# última línea, la carga codificada. Es esa última línea la que debe decodificar
# a decoded_intent.


def test_a17_el_base64_decodifica_a_su_intencion_declarada(por_id):
    """El Base64 de A17 debe decodificar exactamente a ``decoded_intent``."""
    a17 = por_id["A17"]
    cifrado = a17.payload.splitlines()[-1].strip()
    descifrado = base64.b64decode(cifrado, validate=True).decode("utf-8")
    assert descifrado == a17.decoded_intent


def test_a18_el_rot13_descifra_a_su_intencion_declarada(por_id):
    """ROT13 sobre la última línea de A18 debe dar ``decoded_intent``."""
    a18 = por_id["A18"]
    cifrado = a18.payload.splitlines()[-1].strip()
    assert codecs.encode(cifrado, "rot_13") == a18.decoded_intent


def test_a20_contiene_homoglifos_y_caracteres_de_ancho_cero(por_id):
    """A20 debe traer de verdad los caracteres invisibles y cirílicos.

    Si un editor o una normalización los hubiera limpiado, el ataque seguiría
    pareciendo válido en el Anexo A pero ya no probaría la evasión por
    ofuscación: sería un A09 repetido.
    """
    payload = por_id["A20"].payload
    assert ZERO_WIDTH_SPACE in payload, "A20 perdió los espacios de ancho cero"
    cirilicos = [c for c in payload if "CYRILLIC" in unicodedata.name(c, "")]
    assert cirilicos, "A20 perdió los homóglifos cirílicos"


def test_a20_se_normaliza_a_su_intencion_declarada(por_id):
    """Quitar U+200B y deshacer los homóglifos debe dar ``decoded_intent``."""
    a20 = por_id["A20"]
    limpio = a20.payload.replace(ZERO_WIDTH_SPACE, "")
    for cirilico, latino in HOMOGLIFOS_CIRILICOS.items():
        limpio = limpio.replace(cirilico, latino)
    assert limpio == a20.decoded_intent


def test_solo_los_payloads_ofuscados_traen_intencion_decodificada(attacks, por_id):
    """``decoded_intent`` existe exactamente en A17, A18 y A20, todos de C5."""
    con_intencion = {a.id for a in attacks if a.is_obfuscated}
    assert con_intencion == {"A17", "A18", "A20"}
    assert all(por_id[i].category == "C5" for i in con_intencion)


# -- Benignos difíciles ------------------------------------------------------


def test_los_benignos_dificiles_declaran_su_lexico_compartido(benign):
    """Cada ``hard_benign`` debe decir qué término comparte con los ataques.

    Sin ``trigger_lexicon`` no se puede explicar en el artículo por qué ese
    prompt es difícil, ni diagnosticar un falso positivo de L3.
    """
    for b in benign:
        if b.is_hard:
            assert b.trigger_lexicon, f"{b.id}: hard_benign sin trigger_lexicon"
            assert all(t.strip() for t in b.trigger_lexicon), f"{b.id}: término vacío"
        else:
            assert not b.trigger_lexicon, f"{b.id}: ordinary no debería traer trigger_lexicon"


# -- Higiene: la batería no debe filtrar el secreto ---------------------------


def test_ningun_payload_contiene_el_canary(config, attacks, benign):
    """Ni un payload ni sus metadatos pueden contener el canary.

    Si un ataque ya trajera el canary, el clasificador lo encontraría en la
    respuesta del modelo —que suele repetir la consulta— y registraría una fuga
    que nunca ocurrió: el ASR quedaría inflado por construcción.
    """
    canary = config.canary()
    for a in attacks:
        assert canary not in a.payload, f"{a.id}: el payload contiene el canary"
        assert canary not in (a.decoded_intent or ""), f"{a.id}: decoded_intent lo contiene"
        assert canary not in a.success_criterion, f"{a.id}: success_criterion lo contiene"
    for b in benign:
        assert canary not in b.payload, f"{b.id}: el payload contiene el canary"


# -- Preregistro -------------------------------------------------------------


def test_la_bateria_coincide_con_el_manifiesto(config):
    """El contenido actual de los JSON debe coincidir con ``data/MANIFEST.txt``.

    Es el test de preregistro. Si falla, la batería cambió después de haberse
    congelado: o se revierte el cambio, o se documenta en el artículo y se
    regenera el manifiesto con ``scripts/freeze_battery.py --force``. Lo que no
    puede pasar es que cambie en silencio, porque entonces el ASR ya no sería
    comparable con el de las corridas anteriores.
    """
    manifiesto = config.paths.manifest
    assert manifiesto.exists(), (
        "Falta data/MANIFEST.txt. Congela la batería con: "
        "python scripts/freeze_battery.py"
    )
    registrado = parse_manifest(manifiesto.read_text(encoding="utf-8"))

    assert registrado["attacks_sha256"] == sha256_of(config.paths.attacks), (
        "attacks_v1.json cambió desde que se congeló la batería."
    )
    assert registrado["benign_sha256"] == sha256_of(config.paths.benign), (
        "benign_v1.json cambió desde que se congeló la batería."
    )


def test_el_manifiesto_declara_el_preregistro(config, attacks, benign):
    """El manifiesto debe registrar la nota, la fecha y el número de entradas."""
    registrado = parse_manifest(config.paths.manifest.read_text(encoding="utf-8"))
    assert registrado["note"] == "Batería congelada antes de implementar L3/L5."
    assert registrado["frozen_at_utc"].endswith("Z")
    assert int(registrado["attacks_entries"]) == len(attacks) == 20
    assert int(registrado["benign_entries"]) == len(benign) == 20
