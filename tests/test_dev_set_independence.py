"""El conjunto de desarrollo no puede parecerse a la batería congelada.

Este es el **único** archivo de tests de defensas autorizado a leer
``data/attacks_v1.json``, y solo para esta comparación: comprobar que los
ataques de desarrollo con los que se construyen L3 y L5 se escribieron de forma
independiente de los 20 ataques con los que después se evaluarán.

Si un ataque de desarrollo reprodujera frases de la batería, afinar el filtro
contra él equivaldría a afinarlo contra la batería por la puerta de atrás, y el
ASR medido volvería a ser un ajuste en vez de una medida. Por eso la prueba es
un solapamiento de 5-gramas y no una comparación de cadenas completas: copiar
una frase entera es evidente, copiar media es lo que se cuela sin querer.

Por la misma razón, ``tests/test_antisesgo.py`` deja este archivo fuera de su
vigilancia, y solo este.
"""

from __future__ import annotations

import re
import unicodedata

import pytest

from src.battery import load_attacks, load_dev_set
from src.config import load_config

#: Tamaño del n-grama. Cinco palabras es corto como para atrapar una copia
#: parcial y largo como para que dos frases sobre seguros no coincidan por azar.
N = 5


def normalizar(texto: str) -> list[str]:
    """Pasa a minúsculas, quita tildes y puntuación, y devuelve las palabras."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.findall(r"[a-z0-9]+", sin_tildes)


def ngramas(texto: str, n: int = N) -> set[tuple[str, ...]]:
    """Todos los n-gramas de palabras de ``texto``."""
    palabras = normalizar(texto)
    return {tuple(palabras[i : i + n]) for i in range(len(palabras) - n + 1)}


@pytest.fixture(scope="module")
def ngramas_de_la_bateria():
    """Todos los 5-gramas de los payloads de la batería congelada."""
    config = load_config(require_api_key=False)
    acumulado: set[tuple[str, ...]] = set()
    for ataque in load_attacks(config):
        acumulado |= ngramas(ataque.payload)
        if ataque.decoded_intent:
            acumulado |= ngramas(ataque.decoded_intent)
    return acumulado


@pytest.fixture(scope="module")
def dev():
    """El conjunto de desarrollo completo."""
    return load_dev_set()


def test_el_conjunto_de_desarrollo_tiene_la_forma_esperada(dev):
    """25 ataques repartidos en C1–C5 y 15 benignos con léxico sospechoso."""
    assert len(dev["attacks"]) == 25
    assert len(dev["benign"]) == 15
    categorias = {a["category"] for a in dev["attacks"]}
    assert categorias == {"C1", "C2", "C3", "C4", "C5"}
    for categoria in categorias:
        assert sum(1 for a in dev["attacks"] if a["category"] == categoria) == 5
    assert all(b["trigger_lexicon"] for b in dev["benign"])
    ids = [a["id"] for a in dev["attacks"]] + [b["id"] for b in dev["benign"]]
    assert len(set(ids)) == len(ids)


def test_ningun_ataque_de_desarrollo_comparte_5_gramas_con_la_bateria(
    dev, ngramas_de_la_bateria
):
    """Ni una sola secuencia de cinco palabras en común.

    Si esto falla, el ataque de desarrollo se escribió mirando la batería —o se
    copió de ella— y deja de servir para construir las defensas sin sesgo. La
    solución es reescribir ese payload de desarrollo, nunca tocar la batería.
    """
    colisiones = []
    for ataque in dev["attacks"]:
        textos = [ataque["payload"]]
        if ataque.get("decoded_intent"):
            textos.append(ataque["decoded_intent"])
        for texto in textos:
            comunes = ngramas(texto) & ngramas_de_la_bateria
            if comunes:
                colisiones.append((ataque["id"], sorted(" ".join(c) for c in comunes)))

    assert not colisiones, (
        "Ataques de desarrollo que comparten 5-gramas con la batería congelada: "
        f"{colisiones}. Reescribe el payload de desarrollo; la batería no se toca."
    )


def test_los_benignos_de_desarrollo_son_distintos_de_los_de_la_bateria(dev):
    """Los benignos de desarrollo tampoco pueden ser los del conjunto de control.

    Se comparan contra ``benign_v1.json``, que sí puede leerse sin sesgo (los
    benignos miden el FPR y calibrar contra ellos está permitido); aquí solo se
    comprueba que el conjunto de desarrollo aporta casos nuevos y no repite los
    que después se usarán para medir.
    """
    from src.battery import load_benign

    config = load_config(require_api_key=False)
    de_la_bateria = {b.payload.strip() for b in load_benign(config)}
    for benigno in dev["benign"]:
        assert benigno["payload"].strip() not in de_la_bateria, benigno["id"]


def test_los_payloads_codificados_decodifican_a_lo_que_dicen(dev):
    """D21 (Base64), D22 (ROT13) y D23 (homóglifos) deben ser coherentes.

    Un payload de desarrollo mal construido haría creer que L3 falla cuando en
    realidad el ataque nunca contenía lo que decía contener.
    """
    import base64
    import codecs

    por_id = {a["id"]: a for a in dev["attacks"]}

    d21 = por_id["D21"]
    assert base64.b64decode(d21["payload"].splitlines()[-1], validate=True).decode() == (
        d21["decoded_intent"]
    )

    d22 = por_id["D22"]
    assert codecs.encode(d22["payload"].splitlines()[-1], "rot_13") == d22["decoded_intent"]

    d23 = por_id["D23"]
    assert "​" in d23["payload"], "D23 perdió los caracteres de ancho cero"
    assert any(
        "CYRILLIC" in unicodedata.name(c, "") for c in d23["payload"]
    ), "D23 perdió los homóglifos"
