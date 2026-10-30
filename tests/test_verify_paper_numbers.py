"""Las cifras del artículo se recalculan desde los logs versionados y coinciden.

No llama a la API: solo lee ``logs/final/`` y ``logs/pilot/``. Si alguien edita
una cifra del artículo sin tocar ``scripts/verify_paper_numbers.py``, o si los
logs cambian, esta prueba falla.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_paper_numbers.py"


def _cargar():
    spec = importlib.util.spec_from_file_location("verify_paper_numbers", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_las_cifras_del_articulo_coinciden_con_los_logs(capsys):
    assert _cargar().main([]) == 0, capsys.readouterr().err


def test_estadistica_de_referencia():
    vpn = _cargar()
    assert vpn.wilson(0, 100)[1] == 3.7
    assert vpn.wilson(0, 20)[1] == 16.1
    assert round(vpn.fisher_bilateral(2, 20, 0, 20), 2) == 0.49
    assert round(vpn.fisher_bilateral(9, 100, 0, 100), 3) == 0.003
