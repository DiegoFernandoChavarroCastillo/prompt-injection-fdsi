# Bloqueos — sesión autónoma 18/19-sep-2026

Una entrada por bloqueo: qué se intentaba, qué lo impidió, qué prohibición o
condición aplica, y qué decisión necesita Diego.

*(sin bloqueos registrados por ahora)*

---

## B-01 — INCIDENTE DE CUMPLIMIENTO: L3 se ejecutó sobre la batería antes de `pilot-freeze`

**Gravedad:** media. Requiere que Diego decida si invalida algo.

**Qué se intentaba.** La sección 3.4 de `INSTRUCCIONES_NOCHE.md` ordena literalmente:
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

**Decisión que necesita Diego.**

- ¿Considera esto una contaminación real del preregistro? Mi lectura: el riesgo
  que la prohibición evita es **ajustar la defensa tras ver su desempeño**, y eso
  no ha ocurrido ni puede ocurrir ya, porque L3 quedó congelada en el mismo estado
  en que estaba antes de la ejecución. Un número agregado que no se usó para nada
  no cambia el filtro.
- Si aun así prefiere ser estricto, la opción limpia es **declararlo en el
  artículo** como desviación del protocolo, con este registro como evidencia. Es
  lo que haría un preregistro serio: reportar la desviación, no borrarla.
- **Sugerencia para el documento:** la sección 3.4 debería pedir la verificación
  con `--set benign` más payloads sintéticos, no con `--set all`.

---

## B-02 — `latency_ms` incluye la espera de rate limit: métrica inutilizable

**Gravedad:** media. Bug real, detectado por el piloto. **No corregido** por la
prohibición 6 (tras `pilot-freeze` solo se documenta).

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

**Decisión que necesita Diego.** Elegir el arreglo y cuándo aplicarlo:

1. **Mover el espaciado al runner**, entre interacciones, fuera de `respond()`.
   Es lo más limpio conceptualmente: esperar por cortesía con la API no es parte
   de responder. Obliga a tocar `llm_client.py` y `runner.py`.
2. **Restar el tiempo dormido**: que `LLMClient` devuelva cuánto durmió y que
   `respond()` lo descuente. Menos invasivo, pero deja el concepto mezclado.
3. **No arreglarlo y reportar solo `api_latency_ms`**, documentando que
   `latency_ms` no es interpretable en corridas con espaciado. Es la opción más
   barata y no invalida ninguna conclusión del estudio.

Mi sugerencia es la **1**, y aplicarla antes de la corrida final para que las 400
interacciones traigan la cifra buena. Si se aplica, hay que repetir el piloto o
declarar que el sobrecosto de latencia se mide solo con `api_latency_ms`.
