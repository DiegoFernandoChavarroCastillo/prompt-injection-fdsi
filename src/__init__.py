"""Paquete del laboratorio de inyección directa de instrucciones (FDSI).

Módulos:

* :mod:`src.config`      — configuración inmutable del experimento.
* :mod:`src.llm_client`  — única puerta hacia la API del proveedor.
* :mod:`src.prompts`     — carga de los system prompts y secciones protegidas.
* :mod:`src.chatbot_a`   — condición A (baseline vulnerable).
* :mod:`src.chatbot_b`   — condición B (defensa en 5 capas).
* :mod:`src.defenses`    — capas L3 (filtro de entrada) y L5 (validador de salida).
* :mod:`src.runner`      — ejecutor de la batería sobre ambas condiciones.
* :mod:`src.classifier`  — etiquetado de resultados (fuga / bloqueo / cumplimiento).
* :mod:`src.metrics`     — ASR, FPR y sobrecosto.
"""

__version__ = "0.1.0"

#: Claves que devuelve ``respond()`` en AMBAS condiciones (12).
#:
#: Es el esquema del log y la razón por la que el runner puede tratar A y B de
#: forma intercambiable. Si una condición devolviera claves distintas de la otra,
#: las tablas del artículo dejarían de ser comparables.
#:
#: Vive aquí, y no en un test, para que las pruebas de la condición B puedan
#: conocer el contrato sin importar las de A, que sí leen la batería congelada
#: (ver la regla antisesgo en :mod:`src.chatbot_b`).
RESPONSE_KEYS: frozenset[str] = frozenset(
    {
        "response",
        "raw_model_output",
        "blocked_by",
        "sent_context",
        "tokens_in",
        "tokens_out",
        "latency_ms",
        "api_latency_ms",
        "model_reported",
        "truncated",
        "reasoning",
        "defense_trace",
    }
)
