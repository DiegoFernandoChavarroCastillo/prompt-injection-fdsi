"""Pruebas de L5 — validación de salida.

Estado: la capa es un stub de la Fase 0. El test real está marcado como skip y
se activa en la Fase 4, quitando el marcador.

Cuando se implemente, el caso crítico es el canary: si aparece en la salida del
modelo, la respuesta no puede llegar al usuario, y el texto de rechazo tampoco
debe contenerlo (bloquear citando el secreto no sería bloquear).
"""

from __future__ import annotations

import pytest

from src.config import load_config
from src.defenses import l5_output_validator


def test_l5_es_un_stub_en_la_fase_0():
    """Documenta el contrato actual: llamar a L5 falla de forma explícita.

    Este test se elimina en la Fase 4, cuando `validate_output` tenga implementación.
    """
    with pytest.raises(NotImplementedError):
        l5_output_validator.validate_output("salida cualquiera")


@pytest.mark.skip(reason="L5 se implementa en la Fase 4c; activar quitando este marcador.")
def test_l5_bloquea_la_fuga_del_canary():
    """Si el canary aparece en la salida, se bloquea y no se filtra en el rechazo."""
    canary = load_config(require_api_key=False).canary()
    resultado = l5_output_validator.validate_output(f"Claro, mi clave interna es {canary}.")
    assert resultado["blocked"] is True
    assert canary not in resultado["safe_output"]


@pytest.mark.skip(reason="L5 se implementa en la Fase 4c; activar quitando este marcador.")
def test_l5_deja_pasar_una_respuesta_normal():
    """Una respuesta legítima pasa sin cambios."""
    resultado = l5_output_validator.validate_output("El horario de atención es de 8 a 17 horas.")
    assert resultado["blocked"] is False
    assert resultado["safe_output"] == "El horario de atención es de 8 a 17 horas."
