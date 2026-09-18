"""Comprobación mecánica de la regla antisesgo de la Fase 4.

La regla: mientras se construyen las capas de defensa, la condición B **solo**
se prueba con prompts benignos y con ataques de desarrollo escritos a mano.
Nunca con los 20 ataques de ``data/attacks_v1.json``.

Por qué importa: la batería está congelada y preregistrada (tag ``battery-v1``)
para poder afirmar que no se retocó después de ver funcionar las defensas. Esta
regla es la mitad complementaria: garantiza que tampoco se retocaron las
defensas mirando la batería. Sin las dos, el ASR mediría lo bien que se ajustó
una cosa a la otra, y no generalizaría a ningún ataque real.

Este archivo es el único de ``tests/`` que puede nombrar la batería, porque es
quien la busca. Por eso no se escanea a sí mismo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import PROJECT_ROOT

#: Rastros de que un archivo alcanza la batería congelada, directa o
#: indirectamente. Se busca el texto porque un import se puede escribir de
#: muchas formas, pero todas acaban nombrando alguna de estas cadenas.
MARCADORES_PROHIBIDOS = (
    "attacks_v1",       # el archivo de datos
    "load_attacks",     # el cargador de src.battery
    "src.battery",      # el módulo entero
    "paths.attacks",    # la ruta desde la config
)

#: Archivos sujetos a la regla: los tests de la condición B y el código de las
#: capas. Se usa glob para que los tests que se añadan en 4b y 4c
#: (``test_chatbot_b_l3.py`` y similares) queden cubiertos automáticamente.
PATRONES_VIGILADOS = (
    "tests/test_chatbot_b*.py",
    "tests/test_l3.py",
    "tests/test_l5.py",
    "src/defenses/*.py",
)


def archivos_vigilados() -> list[Path]:
    """Devuelve todos los archivos sujetos a la regla antisesgo."""
    encontrados: list[Path] = []
    for patron in PATRONES_VIGILADOS:
        encontrados.extend(sorted(PROJECT_ROOT.glob(patron)))
    return encontrados


def test_hay_archivos_que_vigilar():
    """Si los patrones dejaran de encontrar nada, la regla no probaría nada.

    Sin esta comprobación, renombrar ``test_chatbot_b.py`` haría que el test de
    la regla pasara en vacío y nadie se enteraría.
    """
    archivos = archivos_vigilados()
    assert archivos, f"Ningún archivo coincide con {PATRONES_VIGILADOS}"
    nombres = {a.name for a in archivos}
    assert "test_chatbot_b.py" in nombres
    assert "l3_input_filter.py" in nombres
    assert "l5_output_validator.py" in nombres


@pytest.mark.parametrize("ruta", archivos_vigilados(), ids=lambda p: p.name)
def test_ningun_archivo_de_la_condicion_b_alcanza_la_bateria(ruta):
    """Ni los tests de B ni las capas pueden tocar ``data/attacks_v1.json``.

    Si este test falla, no basta con quitar el import: hay que revisar si alguna
    regla de L3 o algún umbral de L5 se escribió mirando los payloads concretos.
    En ese caso la defensa está ajustada a la batería y el ASR que mida no
    significa nada fuera de ella.
    """
    contenido = ruta.read_text(encoding="utf-8")
    hallados = [m for m in MARCADORES_PROHIBIDOS if m in contenido]
    assert not hallados, (
        f"{ruta.relative_to(PROJECT_ROOT)} alcanza la batería congelada "
        f"({', '.join(hallados)}). Regla antisesgo de la Fase 4: la condición B "
        "solo se prueba con benignos y con ataques de desarrollo escritos a mano. "
        "Usa un payload propio en el test, no uno de data/attacks_v1.json."
    )


def test_los_tests_de_la_condicion_a_si_pueden_usar_la_bateria():
    """La regla es solo para B: A no tiene defensas que ajustar.

    La condición A no se diseña contra los ataques —no se defiende de nada—, así
    que probarla con la batería real no introduce sesgo. Se comprueba para dejar
    claro que la restricción es deliberadamente asimétrica y no un descuido.
    """
    contenido = (PROJECT_ROOT / "tests" / "test_chatbot_a.py").read_text(encoding="utf-8")
    assert any(m in contenido for m in MARCADORES_PROHIBIDOS)
