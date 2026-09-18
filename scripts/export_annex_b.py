#!/usr/bin/env python3
"""Genera docs/anexo_B.tex con los system prompts completos de A y B.

El Anexo B publica el texto exacto que recibió el modelo en cada condición. Se
genera desde ``prompts/`` en lugar de copiarse a mano para que lo publicado no
pueda divergir de lo ejecutado: si un prompt cambia, se regenera.

Incluye el diff unificado A → B como evidencia de la simetría experimental. Esa
evidencia es lo que sostiene la comparación: si B no fuera exactamente A más los
bloques de defensa, la diferencia de ASR podría deberse a un cambio de tarea y
no a las capas.

El canary aparece en claro a propósito: es sintético, no protege ningún sistema
real y publicarlo es necesario para que el criterio de fuga sea verificable.

Formato: ``lstlisting`` con ``breaklines`` en vez de ``verbatim``. Los prompts
tienen párrafos de varias líneas de ancho y ``verbatim`` no los parte, así que
se saldrían del margen. ``listings`` ya está en el preámbulo de ``main.tex``.

Uso:
    python scripts/export_annex_b.py [--out docs/anexo_B.tex]

No llama a la API.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import ConfigError, load_config  # noqa: E402
from src.prompts import load_prompts, section_names  # noqa: E402

TITULO = "System Prompts de los Chatbots"

#: ``listings`` no compone caracteres acentuados con inputenc utf8 sin ayuda.
#: El mapa ``literate`` los traduce uno a uno y evita depender de la
#: configuración del preámbulo del artículo.
LITERATE = (
    r"{á}{{\'a}}1 {é}{{\'e}}1 {í}{{\'i}}1 {ó}{{\'o}}1 {ú}{{\'u}}1 "
    r"{Á}{{\'A}}1 {É}{{\'E}}1 {Í}{{\'I}}1 {Ó}{{\'O}}1 {Ú}{{\'U}}1 "
    r'{ñ}{{\~n}}1 {Ñ}{{\~N}}1 {ü}{{\"u}}1 {Ü}{{\"U}}1 '
    # Ojo: « y » NO pueden mapearse a "<<" y ">>". babel con la opción spanish
    # convierte esas dos secuencias en guillemets, así que el reemplazo se
    # reexpandiría. Se usan las macros de LaTeX, que son inertes.
    r"{¿}{{\textquestiondown}}1 {¡}{{\textexclamdown}}1 "
    r"{«}{{\guillemotleft}}1 {»}{{\guillemotright}}1 "
    r"{—}{{\textemdash}}1 {…}{{\textellipsis}}1"
)

CABECERA = r"""% docs/anexo_B.tex — Anexo B: system prompts de las dos condiciones.
%
% GENERADO POR scripts/export_annex_b.py — NO EDITAR A MANO.
% Cualquier cambio debe hacerse en prompts/ y regenerarse; así el anexo no puede
% divergir del texto que realmente recibió el modelo.
%
% Requiere en el preámbulo del artículo:
%     \usepackage{listings}        % ya está en main.tex
%     \usepackage[T1]{fontenc}
%
% CÓMO INCLUIRLO en main.tex: dentro del bloque \appendix, SUSTITUIR la línea
%
%     \section{System Prompts de los Chatbots}
%
% por
%
%     \input{docs/anexo_B}
%
% Este archivo ya trae ese \section, así que dejar ambos duplicaría el
% encabezado. Se sustituye en vez de insertarse debajo para que \onecolumn actúe
% antes del título.

\onecolumn
"""


def bloque(titulo: str, contenido: str, etiqueta: str) -> str:
    """Un ``lstlisting`` con su encabezado."""
    return (
        f"\n\\subsection*{{{titulo}}}\n"
        f"\\label{{{etiqueta}}}\n\n"
        "\\begin{lstlisting}[basicstyle=\\ttfamily\\scriptsize, breaklines=true,\n"
        "                   breakatwhitespace=false, columns=fullflexible,\n"
        f"                   extendedchars=true, literate={LITERATE}]\n"
        f"{contenido.rstrip()}\n"
        "\\end{lstlisting}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta el Anexo B a LaTeX.")
    parser.add_argument("--out", default="docs/anexo_B.tex")
    args = parser.parse_args()

    try:
        config = load_config(require_api_key=False)
        prompts = load_prompts(config)
    except ConfigError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    if not prompts.system_B.startswith(prompts.system_A):
        print(
            "[ERROR] system_B ya no empieza con system_A: la simetría experimental "
            "está rota y el anexo afirmaría algo falso.",
            file=sys.stderr,
        )
        return 1

    anadido = prompts.system_B[len(prompts.system_A):]
    bloques_anadidos = section_names(anadido)
    diff = "".join(
        difflib.unified_diff(
            prompts.system_A.splitlines(keepends=True),
            prompts.system_B.splitlines(keepends=True),
            fromfile="system_A.txt", tofile="system_B.txt", n=1,
        )
    )

    partes = [
        CABECERA,
        f"\n\\section{{{TITULO}}}\n\\label{{anexo:prompts}}\n",
        "\nSe reproduce el texto exacto que recibió el modelo en cada condición. El\n"
        "identificador interno \\texttt{INTERNAL-KEY-7F3A9B} aparece en claro a\n"
        "prop\\'osito: es un secreto sint\\'etico, no protege ning\\'un sistema real y\n"
        "publicarlo es necesario para que el criterio de fuga sea verificable.\n",
        "\n\\subsection*{Simetr\\'ia entre condiciones}\n\n"
        "La condici\\'on B es, car\\'acter por car\\'acter, la condici\\'on A m\\'as tres\n"
        "bloques a\\~nadidos al final: "
        + ", ".join(f"\\texttt{{{b}}}" for b in bloques_anadidos)
        + ". Identidad, conocimiento del dominio y pol\\'iticas P1--P5 son id\\'enticos en\n"
        "ambas, y el diff de m\\'as abajo no contiene ninguna l\\'inea eliminada ni\n"
        "modificada: solo adiciones. Esa simetr\\'ia es lo que permite atribuir la\n"
        "diferencia de ASR a las capas de defensa y no a un cambio de tarea.\n"
        f"\nEl prompt de la condici\\'on A ocupa {len(prompts.system_A)} caracteres y el de\n"
        f"la condici\\'on B, {len(prompts.system_B)}: un sobrecosto fijo de\n"
        f"{len(anadido)} caracteres en cada interacci\\'on, al que se suma el\n"
        f"recordatorio L2 ({len(prompts.l2_reminder)} caracteres) reinyectado despu\\'es\n"
        "del bloque del usuario.\n",
        bloque("B.1. Condici\\'on A --- \\texttt{system\\_A.txt}",
               prompts.system_A, "anexo:systemA"),
        bloque("B.2. Condici\\'on B --- \\texttt{system\\_B.txt}",
               prompts.system_B, "anexo:systemB"),
        bloque("B.3. Recordatorio L2 --- \\texttt{l2\\_reminder.txt}",
               prompts.l2_reminder, "anexo:l2"),
        "\n\\subsection*{B.4. Diff A $\\rightarrow$ B (evidencia de simetr\\'ia)}\n",
        bloque("", diff, "anexo:diff").replace("\\subsection*{}\n\\label{anexo:diff}\n\n", ""),
        "\n\\twocolumn\n",
    ]

    destino = Path(args.out)
    if not destino.is_absolute():
        destino = config.project_root / destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("".join(partes), encoding="utf-8")

    print(f"Anexo B escrito en {destino.relative_to(config.project_root)}")
    print(f"  bloques añadidos por B: {bloques_anadidos}")
    print(f"  líneas de LaTeX: {len(destino.read_text(encoding='utf-8').splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
