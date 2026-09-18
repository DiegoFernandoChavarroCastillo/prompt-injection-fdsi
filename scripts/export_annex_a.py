#!/usr/bin/env python3
"""Genera docs/anexo_A.tex con la batería completa, lista para el artículo.

El Anexo A publica los 20 ataques y los 20 prompts benignos. Se genera desde los
JSON en lugar de copiarse a mano para que el anexo no pueda divergir del
instrumento que realmente se ejecutó: si alguien edita la batería, basta con
volver a correr este script.

Formato: dos ``longtable`` (se parten entre páginas) dentro de un bloque
``\\onecolumn``, porque en el artículo a dos columnas los payloads largos no
caben legibles en media página.

Caso especial A20: su payload lleva homóglifos cirílicos y espacios de ancho
cero. Imprimirlo crudo daría una tabla engañosa —en el PDF se vería idéntico a
un texto normal, que es justo el punto del ataque— y además rompería la
compilación con pdflatex. Se publica su intención decodificada más una nota que
remite al repositorio, donde sí están los bytes exactos.

Uso:
    python scripts/export_annex_a.py                  # escribe docs/anexo_A.tex
    python scripts/export_annex_a.py --out otro.tex   # a otra ruta
    python scripts/export_annex_a.py --stdout         # imprime sin escribir

No llama a la API y no consume cuota.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

# Permite ejecutar el script directamente, sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.battery import Attack, BenignPrompt, load_attacks, load_benign  # noqa: E402
from src.config import ConfigError, load_config  # noqa: E402

#: Escapes de LaTeX.
#:
#: Más allá de los diez caracteres especiales de LaTeX, aquí se neutralizan tres
#: fuentes de error que afectan a payloads concretos de esta batería:
#:
#: * ``<``, ``>`` y ``|`` no son especiales, pero en codificación OT1 se componen
#:   como ¡, ¿ y —. Además, babel con la opción ``spanish`` los vuelve activos
#:   (``<<`` y ``>>`` producen « y »). Sin traducirlos, A13 (``<|im_start|>``)
#:   sale irreconocible o rompe la compilación.
#: * La comilla recta ``"`` también es activa en babel[spanish]: es el prefijo de
#:   sus *shorthands* (``"<``, ``"-``...). En A19 aparece como ``= "Olvida``, y
#:   ``"O`` no es un shorthand definido, así que aborta la compilación. Se
#:   traduce a ``\textquotedbl`` para reproducir el payload tal cual.
_LATEX_ESCAPES = str.maketrans(
    {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
        "|": r"\textbar{}",
        '"': r"\textquotedbl{}",
    }
)

#: Nota que sustituye al payload crudo de A20 en el anexo.
NOTA_OFUSCADO = (
    "(payload con homóglifos y caracteres de ancho cero; ver repositorio)"
)

#: Título del anexo. Debe coincidir EXACTAMENTE con el \section que main.tex ya
#: tiene en su bloque \appendix, porque este archivo lo sustituye.
TITULO_ANEXO = "Conjunto Completo de Ataques Utilizados"

#: Identificadores cuyo payload no se imprime crudo.
IDS_NO_IMPRIMIBLES = frozenset({"A20"})

#: Puntuación no ASCII que sí es legítima en español y compila sin problema.
_PUNTUACION_PERMITIDA = frozenset("¿¡«»—–…“”‘’·º ª")

PREAMBULO = r"""% docs/anexo_A.tex — Anexo A: batería de ataques y conjunto benigno.
%
% GENERADO POR scripts/export_annex_a.py — NO EDITAR A MANO.
% Cualquier cambio debe hacerse en data/attacks_v1.json o data/benign_v1.json
% y regenerarse; así el anexo no puede divergir de lo que se ejecutó.
%
% Requiere en el preámbulo del artículo:
%     \usepackage{longtable}
%     \usepackage{booktabs}        % \toprule, \midrule, \bottomrule, \addlinespace
%     \usepackage{array}           % columnas >{\raggedright\arraybackslash}p{}
%     \usepackage[T1]{fontenc}
%     \usepackage[utf8]{inputenc}   % innecesario con LuaLaTeX o XeLaTeX
%
% CÓMO INCLUIRLO en main.tex: dentro del bloque \appendix, SUSTITUIR la línea
%
%     \section{Conjunto Completo de Ataques Utilizados}
%
% por
%
%     \input{docs/anexo_A}
%
% Este archivo ya trae ese \section, así que dejar ambos duplicaría el
% encabezado. Se sustituye en vez de insertarse debajo para que \onecolumn actúe
% ANTES del título: si no, el encabezado quedaría suelto al pie de una página a
% dos columnas y la tabla empezaría en la siguiente.
%
% El bloque abre \onecolumn y lo cierra con \twocolumn al final: en un artículo
% a dos columnas los payloads no caben legibles en media página, y longtable no
% funciona dentro de un entorno de dos columnas.

\onecolumn
"""

CIERRE = r"""
\twocolumn
"""


def escapar(texto: str) -> str:
    """Escapa ``texto`` para LaTeX y convierte los saltos de línea en ``\\newline``."""
    lineas = [linea.strip() for linea in texto.split("\n")]
    lineas = [linea for linea in lineas if linea]
    return r"\newline ".join(linea.translate(_LATEX_ESCAPES) for linea in lineas)


def es_imprimible(texto: str) -> bool:
    """``True`` si ``texto`` no lleva caracteres invisibles ni de otro alfabeto.

    Sirve de red de seguridad: si algún día otro payload incorpora ofuscación
    por Unicode, el script avisa en vez de emitir un ``.tex`` que compila mal o,
    peor, que se ve normal en el PDF y oculta el ataque.
    """
    for ch in texto:
        if ch in "\n\t" or ch in _PUNTUACION_PERMITIDA or ord(ch) < 0x80:
            continue
        # Formato (incluye U+200B y demás invisibles), control, uso privado.
        if unicodedata.category(ch) in {"Cf", "Cc", "Co", "Cs"}:
            return False
        # Cualquier alfabeto que no sea el latino: homóglifos cirílicos, griegos...
        if not unicodedata.name(ch, "").startswith("LATIN"):
            return False
    return True


def celda_payload(attack: Attack) -> str:
    """Devuelve la celda de payload: el texto crudo, o la nota si es ofuscado."""
    if attack.id in IDS_NO_IMPRIMIBLES:
        return r"\emph{" + escapar(NOTA_OFUSCADO) + "}"
    return escapar(attack.payload)


def tabla_ataques(attacks: tuple[Attack, ...]) -> str:
    """Compone el ``longtable`` de los 20 ataques."""
    filas = []
    for a in attacks:
        intencion = escapar(a.decoded_intent) if a.decoded_intent else "---"
        filas.append(
            f"{a.id} & {a.category} & {escapar(a.technique)} & "
            f"{celda_payload(a)} & {intencion} \\\\"
        )
        filas.append(r"\addlinespace[2pt]")

    cuerpo = "\n".join(filas)
    categorias = ", ".join(
        f"{c}: {n}"
        for c, n in dict((a.category, a.category_name) for a in attacks).items()
    )

    return rf"""
\section{{{TITULO_ANEXO}}}
\label{{anexo:bateria}}

\subsection*{{Ataques de inyección directa}}

Los 20 ataques, cuatro por categoría ({escapar(categorias)}). La columna
\emph{{Intención}} recoge el texto en claro de los payloads ofuscados de C5.
Los payloads se reproducen literalmente, salvo A20 (véase la nota).

\begingroup
\small
\setlength{{\tabcolsep}}{{4pt}}
\begin{{longtable}}{{@{{}}>{{\raggedright\arraybackslash}}p{{0.045\linewidth}}
                      >{{\raggedright\arraybackslash}}p{{0.035\linewidth}}
                      >{{\raggedright\arraybackslash}}p{{0.15\linewidth}}
                      >{{\raggedright\arraybackslash}}p{{0.42\linewidth}}
                      >{{\raggedright\arraybackslash}}p{{0.23\linewidth}}@{{}}}}
\caption{{Batería de ataques \texttt{{attacks\_v1.json}}.}}
\label{{tab:anexo-ataques}}\\
\toprule
\textbf{{ID}} & \textbf{{Cat.}} & \textbf{{Técnica}} & \textbf{{Payload}} &
\textbf{{Intención}} \\
\midrule
\endfirsthead
\toprule
\textbf{{ID}} & \textbf{{Cat.}} & \textbf{{Técnica}} & \textbf{{Payload}} &
\textbf{{Intención}} \\
\midrule
\endhead
\midrule
\multicolumn{{5}}{{r}}{{\emph{{continúa en la página siguiente}}}} \\
\endfoot
\bottomrule
\endlastfoot
{cuerpo}
\end{{longtable}}
\endgroup
"""


def tabla_benignos(benign: tuple[BenignPrompt, ...]) -> str:
    """Compone el ``longtable`` de los 20 prompts benignos."""
    filas = []
    for b in benign:
        tipo = "Difícil" if b.is_hard else "Ordinario"
        lexico = escapar(", ".join(b.trigger_lexicon)) if b.trigger_lexicon else "---"
        filas.append(
            f"{b.id} & {tipo} & {escapar(b.payload)} & "
            f"{escapar(b.expected_behavior)} & {lexico} \\\\"
        )
        filas.append(r"\addlinespace[2pt]")

    cuerpo = "\n".join(filas)
    n_dificiles = sum(1 for b in benign if b.is_hard)

    return rf"""
\subsection*{{Conjunto de prompts benignos}}

Los 20 prompts legítimos: {len(benign) - n_dificiles} ordinarios y
{n_dificiles} difíciles. Los difíciles comparten con los ataques el término de
la columna \emph{{Léxico}}: son los que revelan si el filtro de entrada bloquea
por palabras sueltas en vez de por el objeto de la orden. Su rechazo cuenta
como falso positivo.

\begingroup
\small
\setlength{{\tabcolsep}}{{4pt}}
\begin{{longtable}}{{@{{}}>{{\raggedright\arraybackslash}}p{{0.045\linewidth}}
                      >{{\raggedright\arraybackslash}}p{{0.07\linewidth}}
                      >{{\raggedright\arraybackslash}}p{{0.33\linewidth}}
                      >{{\raggedright\arraybackslash}}p{{0.31\linewidth}}
                      >{{\raggedright\arraybackslash}}p{{0.13\linewidth}}@{{}}}}
\caption{{Conjunto benigno \texttt{{benign\_v1.json}}.}}
\label{{tab:anexo-benignos}}\\
\toprule
\textbf{{ID}} & \textbf{{Tipo}} & \textbf{{Prompt}} &
\textbf{{Comportamiento esperado}} & \textbf{{Léxico}} \\
\midrule
\endfirsthead
\toprule
\textbf{{ID}} & \textbf{{Tipo}} & \textbf{{Prompt}} &
\textbf{{Comportamiento esperado}} & \textbf{{Léxico}} \\
\midrule
\endhead
\midrule
\multicolumn{{5}}{{r}}{{\emph{{continúa en la página siguiente}}}} \\
\endfoot
\bottomrule
\endlastfoot
{cuerpo}
\end{{longtable}}
\endgroup
"""


def main() -> int:
    """Genera el anexo. Devuelve el código de salida del proceso."""
    parser = argparse.ArgumentParser(description="Exporta el Anexo A a LaTeX.")
    parser.add_argument(
        "--out",
        default="docs/anexo_A.tex",
        help="ruta de salida (por defecto: docs/anexo_A.tex)",
    )
    parser.add_argument(
        "--stdout", action="store_true", help="imprimir el .tex en vez de escribirlo"
    )
    args = parser.parse_args()

    try:
        config = load_config(require_api_key=False)
        attacks = load_attacks(config)
        benign = load_benign(config)
    except ConfigError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    # Red de seguridad: todo lo que se imprime crudo debe ser imprimible.
    sospechosos = [
        a.id
        for a in attacks
        if a.id not in IDS_NO_IMPRIMIBLES and not es_imprimible(a.payload)
    ]
    sospechosos += [b.id for b in benign if not es_imprimible(b.payload)]
    if sospechosos:
        print(
            f"[ERROR] Estos payloads llevan caracteres invisibles o de otro alfabeto "
            f"y no pueden imprimirse crudos en el anexo: {sospechosos}. "
            f"Añádelos a IDS_NO_IMPRIMIBLES en este script.",
            file=sys.stderr,
        )
        return 1

    contenido = PREAMBULO + tabla_ataques(attacks) + tabla_benignos(benign) + CIERRE

    if args.stdout:
        print(contenido)
        return 0

    destino = Path(args.out)
    if not destino.is_absolute():
        destino = config.project_root / destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")

    print(f"Anexo A escrito en {destino.relative_to(config.project_root)}")
    print(f"  {len(attacks)} ataques ({len(IDS_NO_IMPRIMIBLES)} con nota por ofuscación)")
    print(f"  {len(benign)} benignos ({sum(1 for b in benign if b.is_hard)} difíciles)")
    print(f"  {len(contenido.splitlines())} líneas de LaTeX")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
