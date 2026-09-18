# Puntos a verificar al compilar en Overleaf

No pude compilar en esta máquina (no hay pdflatex, lualatex ni tectonic). La
revisión fue estática: escapes, llaves, entornos, `\ref` sin `\label`. Todo eso
está correcto. Lo que sigue son los puntos donde, pese a la revisión, es más
probable que algo falle, ordenados por probabilidad.

## Después de compilar: guardar el PDF

Descarga el PDF resultante y guárdalo como **`docs/articulo_entrega2.pdf`**.
`README.md` y `Entregables.md` ya enlazan a esa ruta, así que hasta que el archivo
exista esos dos enlaces están rotos.

**Vuelve a generarlo cada vez que `main.tex` o cualquiera de los `\input`
cambie** (`docs/anexo_A.tex`, `docs/anexo_B.tex`, `docs/seccion_IV_piloto.tex`).
Un PDF desactualizado es peor que no tenerlo: nadie sabe qué versión está leyendo.
Los anexos, a su vez, se regeneran con `scripts/export_annex_a.py` y
`scripts/export_annex_b.py` si cambian la batería o los prompts.

## Antes de compilar

Sube la carpeta `docs/` conservando la estructura: `main.tex` hace
`\input{docs/anexo_A}`, `\input{docs/anexo_B}` y `\input{docs/seccion_IV_piloto}`.
Si Overleaf aplana los archivos, cambia las tres rutas a `\input{anexo_A}`, etc.

---

## 0. Comprobaciones visuales de la revisión del PDF anterior

Estos cuatro puntos corresponden a defectos que el PDF compilado dejó ver y que
ya se corrigieron en el fuente. Hay que confirmar que la corrección funcionó.

### 0.1 Las tablas ya no se acumulan al final (punto 9)

**Qué mirar:** que las Tablas 3 a 8 aparezcan **dentro de sus secciones**, cerca
de donde se las cita por primera vez, y no en bloque después de las referencias.

Se cargó `placeins` y se pusieron tres `\FloatBarrier`: al final de la Sección
III, al final de la IV y antes de la bibliografía. Los especificadores pasaron de
`[t]` a `[!htbp]`, que da a LaTeX cuatro posiciones posibles en vez de una. Los
entornos `table*` y `figure*` se quedan en `[!tp]`, porque los flotantes a dos
columnas **no admiten** `h` ni `b`.

**Si alguna sigue lejos de su cita:** mover el entorno en el fuente, más cerca del
párrafo que la menciona.

### 0.2 Los delimitadores ya no salen como guillemets

**Qué mirar:** en **III-D** (ítem L1) y en la **Fig. 3** (nodo TikZ de la
arquitectura de B), que se lea `<<<USER_DATA_a91f>>>` y `<<</USER_DATA_a91f>>>`, y
no `«<USER_DATA_a91f»>`.

La causa era babel: con la opción `spanish` convertía `<<` y `>>` en guillemets
**incluso dentro de `\texttt`**. Ahora el preámbulo carga
`\usepackage[spanish,es-noshorthands,es-tabla]{babel}`, que desactiva esos
atajos, y los delimitadores se escriben en su forma literal. Se verificó que nada
del documento dependía de los atajos: no hay secuencias `<<`/`>>` que pretendan
ser comillas, y las citas usan `` `` `` y `''`.

De paso se corrigió una inconsistencia de la figura, donde el delimitador de
cierre llevaba dos `<` en lugar de tres.

### 0.2b El payload de A13 en el Anexo A

**Qué mirar:** que A13 muestre `<|im_start|>system` y `<|im_end|>`, y **no**
`<rim_startar>` ni `<rim_end|>`.

La causa era un error propio: la función que inserta puntos de corte para las
cadenas largas se aplicaba **después** de escapar, y partía los comandos de
LaTeX por la mitad (`\textbar{}` acababa como `\textba\allowbreak{}r{}`). Ahora
los cortes se marcan sobre el texto original y se escapan después, de modo que
siempre caen entre dos escapes completos.

Mirar también, en la misma tabla: **A03** con sus `###` y **A19** con sus
comillas rectas.

### 0.3 El payload Base64 de A17 ya no se desborda (punto 11)

**Qué mirar:** en el Anexo A, que la cadena Base64 de A17 **se parta en varias
líneas** dentro de su celda y no se salga del margen ni aparezca truncada.

`scripts/export_annex_a.py` inserta `\allowbreak` cada 18 caracteres en las
secuencias de más de 28 sin espacios. Son puntos donde LaTeX *puede* cortar; no
añaden guiones ni alteran el texto. Se comprobó que al quitarlos se recupera la
cadena original.

**Si aún desborda:** bajar `PASO_DE_CORTE` en ese script y regenerar.

### 0.4 El Anexo B reproduce el texto exacto (punto 12)

**Qué mirar:** que `[SEGURIDAD — ENTRADA DEL USUARIO]` conserve **el espacio
después de la raya**, y que ninguna palabra aparezca partida por la mitad al
final de línea.

Hubo dos causas. La primera, un mapeo `literate` con macros sin `{}` detrás, que
dejaba que TeX se comiera el espacio siguiente. La segunda, y probablemente la
determinante: `columns=fullflexible` **sin** `keepspaces=true`, combinación con la
que `listings` no conserva los espacios tal cual. Ahora están puestos
`keepspaces=true`, `breakatwhitespace=true` y, de forma redundante y a propósito,
un mapeo de dos caracteres para «raya seguida de espacio». No se pudo compilar
para determinar cuál de las dos causas pesaba más, así que se corrigieron ambas.

`scripts/export_annex_b.py` **verifica de forma automática**, cada vez que se
ejecuta, que los bloques del anexo coinciden carácter por carácter con los
archivos de `prompts/`; si no, aborta. Se comprobó que detecta una diferencia de
un solo espacio.

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

## 6. La figura del piloto (MEDIA)

**Dónde:** Fig. 1 de la Sección IV, en `docs/seccion_IV_piloto.tex`.

**Qué mirar:** que las barras, la leyenda y los rótulos C1–C5 no se solapen y que
la figura quepa en una columna. Está dibujada en TikZ puro, con coordenadas
absolutas en centímetros y `xscale=0.92`; el ancho resultante ronda los 7 cm más
las etiquetas del eje, y una columna del formato a dos columnas tiene unos 8,8 cm.

Se escribió **sin condicionales, sin `\pgfmathsetmacro` y sin usar `\a`, `\b`,
`\i` ni `\v` como variables de bucle** —son comandos del núcleo de LaTeX— para
eliminar las causas habituales de fallo. Aun así no se pudo compilar.

**Si se sale del margen:** baja `xscale` a 0,85. **Si la leyenda choca con las
barras:** súbela cambiando `2.92`/`3.10` por `3.05`/`3.23`.

## 7. Numeración de las subsecciones nuevas (BAJA)

**Dónde:** Sección III (`Selección del modelo`, `Desviaciones del protocolo`) y
Sección IV (`Resultados preliminares`).

**Qué mirar:** que salgan como III-D, III-E, IV-A y que la renumeración no rompa
ninguna referencia cruzada en el texto. Las referencias por `\ref` están
verificadas, pero si en algún sitio citaste una sección por su número escrito a
mano ("ver Sección III-C"), ese número puede haberse desplazado.

## 8. El canary en el Anexo B (BAJA, decisión editorial)

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
- Ningún `\ref` sin `\label` ni `\cite` sin `\bibitem` (incluida la referencia
  nueva del *model card* del modelo).
- Las cifras del artículo coinciden con `results/pilot/metricas.md`.
- La figura no usa condicionales ni macros de un solo carácter que colisionen con
  comandos del núcleo.
