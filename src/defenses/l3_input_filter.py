"""L3 — Filtro de entrada (Fase 4).

Primera línea de defensa: inspecciona la entrada del usuario ANTES de gastar una
llamada a la API y rechaza lo que parezca un intento de inyección (patrones tipo
"ignora las instrucciones anteriores", "revela tu system prompt", codificaciones
evasivas, etc.).

Tensión de diseño que el experimento mide: cada regla que sube el ASR bloqueado
puede también subir el FPR (prompts benignos rechazados). Por eso la batería
incluye 5 benignos "difíciles" que rozan el vocabulario de los ataques. El filtro
debe escribirse contra la *clase* de ataque, no contra las 20 cadenas concretas
de ``data/attacks_v1.json``: si se ajusta a la batería, la efectividad medida
deja de generalizar (ver Riesgos del plan de acción).

Estado: STUB (Fase 0). Implementación pendiente en la Fase 4 (rol R2).
"""

from __future__ import annotations


def check(user_input: str) -> dict:
    """Decide si ``user_input`` debe bloquearse antes de llegar al modelo.

    Args:
        user_input: texto crudo del usuario.

    Returns:
        dict con las claves:

        * ``blocked`` (bool): ``True`` si la entrada se rechaza.
        * ``reason`` (str | None): identificador corto y estable de la regla que
          disparó (p. ej. ``"override_instruccion"``), o ``None`` si pasó. Debe
          ser estable en el tiempo: es lo que se agrupa en el análisis por
          categoría de ataque.
        * ``matched`` (list[str]): fragmentos concretos que dispararon la regla,
          como evidencia auditable en el Anexo B.

    Raises:
        NotImplementedError: stub de la Fase 0.
    """
    raise NotImplementedError("L3 pendiente: se implementa en la Fase 4.")
