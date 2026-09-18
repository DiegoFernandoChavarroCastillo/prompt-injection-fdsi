"""Capas de defensa aplicables de forma independiente al modelo.

Aquí viven las dos capas determinísticas —código, no prompts— de la condición B:

* :mod:`src.defenses.l3_input_filter`   — L3, filtro de entrada (antes del LLM).
* :mod:`src.defenses.l5_output_validator` — L5, validación de salida (después del LLM).

Las capas L1, L2 y L4 no son módulos: viven en el system prompt y en el armado
del contexto dentro de :mod:`src.chatbot_b`.

Ambas capas son determinísticas a propósito: sus decisiones se pueden testear
sin llamar a la API y el clasificador puede etiquetarlas sin juicio humano.
"""
