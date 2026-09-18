"""Paquete del laboratorio de inyección directa de instrucciones (FDSI).

Módulos:

* :mod:`src.config`      — configuración inmutable del experimento.
* :mod:`src.llm_client`  — única puerta hacia la API del proveedor.
* :mod:`src.chatbot_a`   — condición A (baseline vulnerable).
* :mod:`src.chatbot_b`   — condición B (defensa en 5 capas).
* :mod:`src.defenses`    — capas L3 (filtro de entrada) y L5 (validador de salida).
* :mod:`src.runner`      — ejecutor de la batería sobre ambas condiciones.
* :mod:`src.classifier`  — etiquetado de resultados (fuga / bloqueo / cumplimiento).
* :mod:`src.metrics`     — ASR, FPR y sobrecosto.
"""

__version__ = "0.1.0"
