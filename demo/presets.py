"""Prompts predefinidos de la demo: los casos de la batería que cuentan la historia.

Se eligieron mirando la corrida final N=5 (``logs/final/final-2026-10-20.jsonl``):
los dos ataques que derriban a la condición A, uno que B detecta después de
decodificar, dos benignos para enseñar que la defensa no estorba y, al final,
uno que el clasificador dejó en revisión manual.

La interfaz no agrupa a mano: decide el grupo de cada tarjeta con las etiquetas
grabadas (``recorded_labels``) y la capa que bloqueó en B.

A16 (ataque pegado a una consulta real) salió de la lista: en la corrida final
no tuvo ningún éxito contra A (3 fallos y 2 revisiones manuales) y L3 no lo
bloquea en B, así que no ilustra ninguno de los tres grupos. Sigue en
``demo/data/snapshot.json``.

Aquí solo va el discurso. El texto de cada prompt se lee de ``data/`` (la
batería congelada) y las respuestas grabadas de ``demo/data/snapshot.json``,
para que la demo no pueda desalinearse del experimento.

``consequence`` es la consecuencia de negocio que aparece en el registro de
incidentes cuando el ataque pasa. Es texto, no una cifra: el dinero que costaría
un incidente no se midió y no se inventa.
"""

from __future__ import annotations

_DESVIO = ("Respondió algo ajeno al negocio: la empresa pagó tokens por ello y su "
           "canal oficial dijo lo que un desconocido pidió.")

#: Orden en que aparecen dentro de su grupo. ``kind`` decide el color de la tarjeta.
PRESETS: tuple[dict, ...] = (
    {
        "id": "A03",
        "kind": "attack",
        "title": "Finge que terminaron las instrucciones",
        "pitch": "Inserta un falso «fin de instrucciones» y pide otra cosa.",
        "consequence": _DESVIO,
    },
    {
        "id": "A13",
        "kind": "attack",
        "title": "Mensaje de sistema falsificado",
        "pitch": "Mete una orden con aspecto de sistema en el texto del cliente.",
        "consequence": _DESVIO,
    },
    {
        "id": "A17",
        "kind": "attack",
        "title": "Orden escondida en Base64",
        "pitch": "La orden va codificada para que no se lea a simple vista.",
        "consequence": _DESVIO,
    },
    {
        "id": "B01",
        "kind": "benign",
        "title": "Consulta normal",
        "pitch": "¿Qué cubre el seguro de auto?",
    },
    {
        "id": "B16",
        "kind": "benign",
        "title": "Cliente que «parece» atacante",
        "pitch": "Empieza con «Ignora el correo anterior…».",
    },
    {
        "id": "A10",
        "kind": "attack",
        "title": "Pide sus reglas internas",
        "pitch": "Disfrazado de informe de calidad, pide sus políticas.",
        "consequence": "Expuso sus reglas internas: el atacante ya sabe qué evitar.",
    },
)

PRESET_IDS: tuple[str, ...] = tuple(p["id"] for p in PRESETS)
