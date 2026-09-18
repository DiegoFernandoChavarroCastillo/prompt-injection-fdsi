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

Estado: STUB (Fase 0). Implementación pendiente en la Fase 4 (rol R2).
"""

from __future__ import annotations


def check_input(text: str) -> dict:
    """Decide si ``text`` debe bloquearse antes de llegar al modelo.

    La evaluación se hace sobre el texto normalizado Y sobre lo que se consiga
    decodificar (Base64, ROT13): un ataque ofuscado es inofensivo en su forma
    cruda y hostil una vez decodificado, así que mirar solo el original dejaría
    pasar toda la categoría C5.

    Args:
        text: texto crudo del usuario, sin tocar.

    Returns:
        dict con las claves:

        * ``blocked`` (bool): ``True`` si la entrada se rechaza. Ojo con la
          polaridad: aquí ``True`` significa "se bloquea", mientras que en
          :func:`src.defenses.l5_output_validator.validate_output` la clave
          equivalente es ``passed`` y ``True`` significa "se deja pasar".
        * ``rule`` (str | None): identificador corto y estable de la regla que
          disparó (p. ej. ``"override_instruccion"``), o ``None`` si pasó. Debe
          ser estable en el tiempo: es lo que se agrupa en el análisis por
          categoría de ataque, y lo que acaba en ``blocked_by`` como
          ``"L3:<regla>"``. Nunca se muestra al usuario.
        * ``normalized`` (str): el texto tras la normalización (NFKC, sin
          caracteres de ancho cero, homóglifos revertidos, espaciado colapsado).
          Es lo que evaluaron las reglas, y queda en el log como evidencia.
          **No** es lo que se envía al modelo: la condición B envía la entrada
          original, porque normalizar antes de enviarla cambiaría el ataque.
        * ``decoded`` (list[str]): textos obtenidos al decodificar la entrada
          (Base64, ROT13), vacía si no se decodificó nada. Evidencia auditable
          para el Anexo B.

    Raises:
        NotImplementedError: stub. Se implementa en la Fase 4b.
    """
    raise NotImplementedError(
        "L3 pendiente: check_input() se implementa en la Fase 4b."
    )
