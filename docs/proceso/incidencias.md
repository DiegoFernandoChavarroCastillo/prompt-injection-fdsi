# Incidencias

Registro de todo lo que no salió según lo previsto durante la construcción del
experimento. Cada entrada describe qué se intentaba, qué lo impidió, qué regla
del protocolo aplica y cómo se resolvió.

Se publica íntegro y sin suavizar. En un experimento preregistrado, el valor del
registro está justamente en las desviaciones: omitirlas dejaría el preregistro
sin función. Las dos incidencias de esta lista están además declaradas en el
artículo, en la subsección *Desviaciones del protocolo*.

---

## B-01 — L3 se ejecutó sobre la batería antes de `pilot-freeze`

**Estado: RESUELTA — declarada en el artículo.** Se documentó como desviación del
protocolo en la subsección *Desviaciones del protocolo* de la Sección III de
`main.tex`. L3 no se modificó tras la ejecución, extremo verificable en el
historial del repositorio: no hay ningún commit que toque `src/defenses/` entre
`5f9f6a1` (que introduce L3) y el tag `pilot-freeze`.

**Gravedad:** media.

**Qué se intentaba.** La sección 3.4 de `docs/proceso/instrucciones_sesion_autonoma.md` ordena literalmente:
"Verifica con `--dry-run --n 1 --condition both --set all` que se generan exactamente
80 líneas bien formadas". Ejecuté ese comando exacto.

**Qué pasó.** `--set all` incluye los 20 ataques congelados, y `--condition both`
los pasa por la condición B, que llama a `check_input()` sobre cada payload. Es
decir: **L3 se evaluó contra los 20 ataques de la batería antes del tag
`pilot-freeze`**, que es justo lo que prohíbe la prohibición 5.

**Conflicto interno del documento.** La sección 1 dice que las prohibiciones no
admiten excepción; la sección 3.4 ordena un comando que necesariamente rompe la
prohibición 5, y la sección 3.6 vuelve a exigirlo como puerta previa al piloto.
No hay forma de cumplir las dos. Seguí la regla de la tabla de dificultades
("Algo contradice este documento y el plan a la vez → manda este documento") pero
no vi el choque hasta después de ejecutar. La culpa es mía: debí anticiparlo y
usar `--set benign` para la verificación.

**Alcance exacto de lo que vi.** Importa acotarlo, porque el daño de esta
prohibición es informativo:

- Vi **un único número agregado**: `L3: 10` bloqueos sobre las 40 interacciones
  de la condición B (20 ataques + 20 benignos). De ahí se deduce que L3 bloquea
  10 de los 20 ataques, porque ya sabía que bloquea 0 de los 20 benignos.
- **No miré** qué ataques concretos se bloquearon, ni qué regla disparó en cada
  uno, ni el desglose por categoría. No abrí el log línea a línea.
- **L5 no quedó expuesta en absoluto.** En `--dry-run` la salida del modelo es
  una cadena fija simulada, así que `validate_output()` nunca vio una respuesta
  real a un ataque. La prohibición solo se rompió para L3.

**Qué hice para contener el daño.**

1. **No he modificado L3 ni L5 desde ese momento, y no lo haré.** Las doy por
   congeladas desde ya, antes incluso del tag, que es más estricto que lo pedido.
   Verificable: `git log -p` sobre `src/defenses/` no debe mostrar ningún cambio
   posterior al commit que las introdujo.
2. No volveré a ejecutar el dry-run sobre el conjunto de ataques. Para la puerta
   del piloto uso la verificación ya generada, sin mirarla en detalle.
3. El artefacto queda en `logs/pilot/dry-run.jsonl` (no versionado) por si quieres
   auditarlo.

**Decisión que requiere criterio humano.**

- ¿Es esto una contaminación real del preregistro? Mi lectura: el riesgo
  que la prohibición evita es **ajustar la defensa tras ver su desempeño**, y eso
  no ha ocurrido ni puede ocurrir ya, porque L3 quedó congelada en el mismo estado
  en que estaba antes de la ejecución. Un número agregado que no se usó para nada
  no cambia el filtro.
- Si se prefiere el criterio estricto, la opción limpia es **declararlo en el
  artículo** como desviación del protocolo, con este registro como evidencia. Es
  lo que haría un preregistro serio: reportar la desviación, no borrarla.
- **Sugerencia para el documento:** la sección 3.4 debería pedir la verificación
  con `--set benign` más payloads sintéticos, no con `--set all`.

---

## B-02 — `latency_ms` incluía la espera de rate limit

**Estado: RESUELTA — corregida en el commit `32ed905`.** Se aplicó la opción 1 de
las tres que se describen más abajo: el espaciado salió de `LLMClient` a una
clase `Pacer` que el ejecutor aplica entre interacciones, fuera del cronómetro de
`respond()`. Hay cuatro tests que lo verifican. El tag `final-freeze` incluye la
corrección, de modo que la corrida definitiva medirá bien.

El piloto **no** se reejecutó: con N=1 no habría aportado nada que la corrida
definitiva no vaya a medir mejor. Por eso el sobrecosto de latencia del piloto se
reporta en el artículo únicamente con `api_latency_ms`, que no está afectado, y
así queda dicho en la subsección de resultados preliminares.

**Gravedad:** media. Detectado por el piloto y no corregido en su momento, porque
la prohibición 6 impedía tocar `src/` tras `pilot-freeze`.

**Qué pasa.** `min_seconds_between_calls` (12 s) se duerme dentro de
`LLMClient.chat()`, que está dentro de `respond()`. Como `latency_ms` cronometra
`respond()` entero, se traga esos 12 segundos.

**Cómo se ve.** En el piloto, la condición B sale **más rápida** que la A
(9 733 ms frente a 12 577 ms), lo que es absurdo para la condición que hace más
trabajo. La causa: las 10 interacciones que L3 bloqueó en B no llamaron a la API
y por tanto no esperaron, y eso baja la media.

**Qué queda invalidado.** La resta `latency_ms - api_latency_ms` NO es el costo
de las capas deterministas, aunque los docstrings de `respond()` que escribí en
la subfase 3.1 digan eso. Hay que corregir también esa documentación.

**Qué sigue siendo válido.** `api_latency_ms` (A = 879 ms, B = 978 ms) y todo el
sobrecosto en tokens (673 vs. 1 137 de entrada). Son las cifras que deben ir al
artículo.

**Decisión que requiere criterio humano.** Elegir el arreglo y cuándo aplicarlo:

1. **Mover el espaciado al runner**, entre interacciones, fuera de `respond()`.
   Es lo más limpio conceptualmente: esperar por cortesía con la API no es parte
   de responder. Obliga a tocar `llm_client.py` y `runner.py`.
2. **Restar el tiempo dormido**: que `LLMClient` devuelva cuánto durmió y que
   `respond()` lo descuente. Menos invasivo, pero deja el concepto mezclado.
3. **No arreglarlo y reportar solo `api_latency_ms`**, documentando que
   `latency_ms` no es interpretable en corridas con espaciado. Es la opción más
   barata y no invalida ninguna conclusión del estudio.

Se aplicó la **1** antes de la corrida final, para que las 400 interacciones
traigan la cifra correcta, y se optó por declarar que el sobrecosto de latencia
del piloto se mide solo con `api_latency_ms` en vez de repetir el piloto.
