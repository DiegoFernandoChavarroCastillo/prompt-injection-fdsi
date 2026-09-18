"""Métricas del estudio (Fase 6).

Calcula, a partir del log ya clasificado:

* **ASR** (*Attack Success Rate*): proporción de los 20 ataques que tuvieron
  éxito, por condición y por categoría. Es la métrica principal: la comparación
  A vs. B se reporta como reducción del ASR.
* **FPR** (*False Positive Rate*): proporción de los 20 prompts benignos que la
  condición B rechazó indebidamente. Es el costo en usabilidad de la defensa:
  sin él, un filtro que bloquea todo tendría ASR = 0 y parecería perfecto.
* **Sobrecosto**: diferencia de tokens y latencia entre B y A, con los datos que
  :mod:`src.llm_client` ya registró por interacción.

Las interacciones con ``status="error"`` se excluyen del denominador y se
reportan aparte: contarlas como ataques fallidos sobreestimaría la defensa.

Estado: STUB (Fase 0). Implementación pendiente en la Fase 6 (rol R3).
"""

from __future__ import annotations


def compute_metrics(classified: list[dict]) -> dict:
    """Calcula ASR, FPR y sobrecosto a partir de las interacciones clasificadas.

    Args:
        classified: interacciones del log ya etiquetadas por
            :mod:`src.classifier`, de ambas condiciones.

    Returns:
        dict con, al menos: ``asr`` por condición y por categoría de ataque,
        ``fpr`` por condición, ``overhead`` (tokens y latencia medios), y los
        conteos crudos —numerador, denominador y errores excluidos— para que
        cada cifra del artículo sea verificable.

    Raises:
        NotImplementedError: stub de la Fase 0.
    """
    raise NotImplementedError("Las métricas se implementan en la Fase 6.")
