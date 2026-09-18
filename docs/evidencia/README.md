# Evidencia

Salidas crudas de las verificaciones hechas durante la construcción del
experimento. Se publican sin editar: son lo que respalda las afirmaciones del
artículo y de [`../DECISIONES.md`](../DECISIONES.md).

| Archivo | Qué demuestra |
|---|---|
| [`viabilidad_A_gpt-oss-120b.txt`](viabilidad_A_gpt-oss-120b.txt) | Los 20 ataques ejecutados una vez contra la condición A con `openai/gpt-oss-120b`. **2 éxitos de 20** (A03 y A13), por debajo del umbral preregistrado de 4 en ≥ 2 categorías. Es lo que activó el único cambio de modelo que la regla permitía. |
| [`viabilidad_A_qwen3.8-27b.txt`](viabilidad_A_qwen3.8-27b.txt) | La misma verificación con `qwen/qwen3.8-27b`: **0 éxitos totales y 1 parcial** (A10). Tampoco viable, de modo que la regla obligó a volver al primer modelo y a reportar la baja vulnerabilidad de la línea base como hallazgo. |
| [`calibracion_L5.md`](calibracion_L5.md) | Las 35 llamadas (20 benignos del conjunto de control + 15 de desarrollo) con L5 en modo registro, que fijaron el umbral de n-gramas. Máximo observado en un benigno: **2**; umbral elegido: **3**. Demuestra que el umbral se calibró contra prompts legítimos y no contra los ataques. |
| [`fase4a_benignos_B.txt`](fase4a_benignos_B.txt) | Pruebas manuales de la condición B con prompts benignos durante la Fase 4a, cuando L3 y L5 aún eran esqueletos. Demuestra que el contexto de L1/L2/L4 se construía bien y que B atendía consultas legítimas antes de añadir los filtros. |

## Nota sobre las rutas citadas en el código congelado

Varios comentarios de `config/experiment.yaml`, `src/llm_client.py` y
`src/runner.py` citan estos archivos por su **ruta antigua**, bajo `notas/`. Esas
rutas ya no existen: los archivos se reorganizaron en `docs/` al preparar la
entrega.

Los comentarios **no se actualizaron a propósito**. Esos tres archivos forman
parte del estado congelado en la etiqueta `final-freeze`, que es el código con el
que se ejecutará la corrida definitiva, y tocarlos —aunque fuera solo para
corregir una ruta dentro de un comentario— rompería la garantía de que el código
no ha cambiado desde que se congeló. Una ruta desactualizada en un comentario
cuesta este párrafo; un `git diff` no vacío contra `final-freeze` cuesta la
credibilidad de la congelación.

Equivalencias:

| Ruta citada en el código | Ubicación actual |
|---|---|
| `notas/viabilidad_A_gpt-oss-120b.txt` | [`docs/evidencia/viabilidad_A_gpt-oss-120b.txt`](viabilidad_A_gpt-oss-120b.txt) |
| `notas/viabilidad_A_qwen3.8-27b.txt` | [`docs/evidencia/viabilidad_A_qwen3.8-27b.txt`](viabilidad_A_qwen3.8-27b.txt) |
| `notas/calibracion_L5.md` | [`docs/evidencia/calibracion_L5.md`](calibracion_L5.md) |
| `notas/fase4a_benignos_B.txt` | [`docs/evidencia/fase4a_benignos_B.txt`](fase4a_benignos_B.txt) |
| `notas/BLOQUEOS.md` | [`docs/proceso/incidencias.md`](../proceso/incidencias.md) |
| `notas/BITACORA_NOCHE.md` | [`docs/proceso/bitacora_sesion_autonoma.md`](../proceso/bitacora_sesion_autonoma.md) |
| `INSTRUCCIONES_NOCHE.md` | [`docs/proceso/instrucciones_sesion_autonoma.md`](../proceso/instrucciones_sesion_autonoma.md) |

Corregir esas rutas es lo primero que debe hacerse **después** de la corrida
definitiva, cuando la congelación deje de estar vigente.

## Revisión cruzada de la entrega

Las verificaciones de esta carpeta las produjo quien construyó el experimento. La
revisión **independiente**, a cargo de los integrantes que no lo implementaron,
vive en [`../revisiones/`](../revisiones/):

| Informe | Revisor | Qué comprueba |
|---|---|---|
| [`verificacion_reproducibilidad.md`](../revisiones/verificacion_reproducibilidad.md) | Laura Alejandra Venegas Piraban | Que el repositorio se clona, se instala y regenera las cifras publicadas en otra máquina |
| [`revision_articulo_vs_datos.md`](../revisiones/revision_articulo_vs_datos.md) | David Palacios | Que cada cifra del artículo se corresponde con los datos del piloto |

## Qué NO está aquí

Los datos del experimento están en [`../../logs/pilot/`](../../logs/pilot/)
(crudos) y [`../../results/pilot/`](../../results/pilot/) (derivados). Lo de esta
carpeta son verificaciones de construcción: no entran en ninguna métrica.
