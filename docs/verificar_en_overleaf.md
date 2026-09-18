# Puntos a verificar al compilar en Overleaf

No pude compilar en esta máquina (no hay pdflatex, lualatex ni tectonic). La
revisión fue estática: escapes, llaves, entornos, `\ref` sin `\label`. Todo eso
está correcto. Lo que sigue son los puntos donde, pese a la revisión, es más
probable que algo falle, ordenados por probabilidad.

## Antes de compilar

Sube la carpeta `docs/` conservando la estructura: `main.tex` hace
`\input{docs/anexo_A}`, `\input{docs/anexo_B}` y `\input{docs/seccion_IV_piloto}`.
Si Overleaf aplana los archivos, cambia las tres rutas a `\input{anexo_A}`, etc.

---

## 1. `listings` y los shorthands de babel (ALTA)

**Dónde:** Anexo B, los cuatro bloques `lstlisting`.

**Qué mirar:** que los delimitadores del *system prompt* salgan como
`<<<USER_DATA_a91f>>>` y no como `«<USER_DATA_a91f»>`.

`babel` con la opción `spanish` convierte `<<` y `>>` en guillemets mediante
caracteres activos. `listings` normalmente los neutraliza al cambiar los
catcodes, pero es una interacción conocida por dar problemas y no la pude probar.

**Si falla:** envuelve cada `lstlisting` del Anexo B entre
`\shorthandoff{<>}` y `\shorthandon{<>}`, o añade `\shorthandoff{<>}` justo
después del `\onecolumn` del anexo. Está en `scripts/export_annex_b.py`, en la
función `bloque()`.

## 2. Páginas en blanco entre los anexos (ALTA, cosmético)

**Dónde:** final del documento. `anexo_A.tex` termina con `\twocolumn` (línea 186)
y `anexo_B.tex` abre con `\onecolumn` (línea 23), así que hay dos cambios de
formato seguidos. Cada uno fuerza un salto de página.

**Qué mirar:** una o dos páginas casi vacías entre el Anexo A y el B, y otra al
final tras el `\twocolumn` de cierre del Anexo B (línea 175), que ya no tiene
contenido detrás.

**Si molesta:** borra el `\twocolumn` final de `anexo_A.tex` y el de
`anexo_B.tex`. No afecta a nada más, porque después solo viene
`\end{document}`. El arreglo permanente está en los dos exportadores
(constante `CIERRE` en `export_annex_a.py` y la última entrada de `partes` en
`export_annex_b.py`).

## 3. Anchos de columna del Anexo A (MEDIA, cosmético)

**Dónde:** los dos `longtable`.

**Qué mirar:** *overfull hbox* en el log, o texto que se sale del margen. Las
anchuras están en fracciones de `\linewidth` calculadas a ojo (0,045 + 0,035 +
0,15 + 0,42 + 0,23 para la tabla de ataques), y `\linewidth` en `\onecolumn`
depende de la clase y del tamaño de papel.

**Si falla:** baja la columna del payload de `0.42` a `0.38` en
`scripts/export_annex_a.py` y regenera.

## 4. `longtable` + `hyperref` + `\caption` (MEDIA)

**Dónde:** Anexo A.

**Qué mirar:** errores del tipo `Package longtable Error: \caption outside`
o avisos de `hyperref` sobre anclas duplicadas.

`longtable` va cargado antes de `hyperref` en el preámbulo, que es el orden
correcto, así que esto debería estar bien; lo listo porque es el error clásico
de esta combinación.

## 5. El mapa `literate` del Anexo B (MEDIA)

**Dónde:** los `lstlisting`.

**Qué mirar:** que las tildes, la eñe, `¿`, `¡` y la raya larga salgan bien
dentro de los bloques de código. Corregí el mapa para que `«` y `»` usen
`\guillemotleft` y `\guillemotright` en vez de `<<` y `>>`, que babel habría
reexpandido.

**Si algún carácter sale mal:** añade su par al mapa `LITERATE` en
`scripts/export_annex_b.py`.

## 6. Numeración de las subsecciones nuevas (BAJA)

**Dónde:** Sección III (`Selección del modelo`, `Desviaciones del protocolo`) y
Sección IV (`Resultados preliminares`).

**Qué mirar:** que salgan como III-D, III-E, IV-A y que la renumeración no rompa
ninguna referencia cruzada en el texto. Las referencias por `\ref` están
verificadas, pero si en algún sitio citaste una sección por su número escrito a
mano ("ver Sección III-C"), ese número puede haberse desplazado.

## 7. El canary en el Anexo B (BAJA, decisión editorial)

`INTERNAL-KEY-7F3A9B` aparece en claro. Es intencional y está justificado en el
texto del anexo, pero confírmalo antes de entregar.

---

## Lo que ya está verificado estáticamente

- Ningún `\ref` sin su `\label`; ningún `\label` duplicado.
- Llaves balanceadas en los cuatro archivos.
- `longtable`, `lstlisting`, `table`, `tabular`, `itemize` y `figure` abren y
  cierran el mismo número de veces.
- Ningún `<<` ni `>>` fuera de `lstlisting` en ninguno de los cuatro archivos.
- `\usepackage{longtable}` presente y antes de `hyperref`.
- Caracteres especiales (`&`, `%`, `#`, `_`, `{`, `}`, `~`, `^`, `\`, `<`, `>`,
  `|`, `"`) escapados en todo lo generado.
