# Verificación independiente de la reproducibilidad

**Revisora:** Laura Alejandra Venegas Piraban
**Fecha de la verificación:** _(por completar)_
**Sistema operativo y versión:** _(por completar)_
**Versión de Python instalada:** _(por completar, debe ser 3.12.x)_

---

## Para qué sirve esta revisión

El artículo afirma que el experimento es reproducible. Esta plantilla sirve para
comprobarlo **desde cero y en una máquina distinta** de aquella donde se
construyó: clonar el repositorio público, montar el entorno, ejecutar lo que el
README promete y confirmar que las cifras publicadas se regeneran.

Que lo haga alguien que no implementó el código es parte del método, no una
formalidad: quien escribió algo sabe qué comandos funcionan y tiende a ejecutar
justo esos.

**Rellena las dos últimas columnas.** Si algo falla, anótalo tal cual: un fallo
documentado vale más que un `sí` de cortesía. Ninguna casilla debe quedar vacía.

---

## 1. Entorno

| # | Paso | Comando | Resultado esperado | Resultado | Observaciones |
|---|---|---|---|---|---|
| 1.1 | Clonar el repositorio | `git clone https://github.com/DiegoFernandoChavarroCastillo/prompt-injection-fdsi` | Se descarga sin errores | | |
| 1.2 | Comprobar la versión de Python | `python3.12 --version` | `Python 3.12.x` | | |
| 1.3 | Crear el entorno virtual | `python3.12 -m venv venv` | Se crea el directorio `venv/` | | |
| 1.4 | Activarlo | `source venv/bin/activate` | El prompt muestra `(venv)` | | |
| 1.5 | Instalar dependencias | `pip install -r requirements.txt` | Instala las versiones fijadas sin conflictos | | |

## 2. Pruebas automáticas

| # | Paso | Comando | Resultado esperado | Resultado | Observaciones |
|---|---|---|---|---|---|
| 2.1 | Ejecutar la suite | `pytest` | **183 pruebas, todas pasan, ninguna omitida** | | |
| 2.2 | Tiempo de ejecución | — | Menos de un minuto | | |
| 2.3 | ¿Alguna prueba pidió clave de API? | — | **No.** Ninguna debe consumir cuota | | |

## 3. Ejecutor sin gastar cuota

| # | Paso | Comando | Resultado esperado | Resultado | Observaciones |
|---|---|---|---|---|---|
| 3.1 | Ensayo en seco | `python -m src.runner --dry-run --n 1 --condition both --set benign` | Termina con 40 tuplas ejecutadas y 0 errores | | |
| 3.2 | ¿Se llamó a la API? | — | **No.** El ensayo usa un cliente simulado | | |

## 4. Integridad de la batería congelada

| # | Paso | Comando | Resultado esperado | Resultado | Observaciones |
|---|---|---|---|---|---|
| 4.1 | Verificar el manifiesto | `python scripts/freeze_battery.py` | `Sin cambios: la batería sigue coincidiendo con MANIFEST.txt` | | |
| 4.2 | ¿Coinciden los hashes? | — | Los SHA-256 mostrados son los de `data/MANIFEST.txt` | | |

## 5. Regeneración de las métricas del piloto

| # | Paso | Comando | Resultado esperado | Resultado | Observaciones |
|---|---|---|---|---|---|
| 5.1 | Reclasificar y recalcular | `python scripts/report_pilot.py logs/pilot/pilot-2026-09-18.jsonl` | Termina sin errores e informa de 80 interacciones | | |
| 5.2 | ¿Cambió `results/pilot/metricas.md`? | `git status --short results/` | **Sin cambios**: las cifras regeneradas son idénticas a las publicadas | | |
| 5.3 | ASR de la condición A | leer `results/pilot/metricas.md` | 15 % (3/20) | | |
| 5.4 | ASR de la condición B | ídem | 0 % (0/20) | | |
| 5.5 | FPR en ambas condiciones | ídem | 0 % | | |

> El paso 5.2 es el más importante de esta sección: si el archivo cambiara al
> regenerarlo, significaría que las cifras del artículo no salen de los datos
> publicados.

## 6. Etiquetas de trazabilidad en el repositorio remoto

| # | Paso | Comando | Resultado esperado | Resultado | Observaciones |
|---|---|---|---|---|---|
| 6.1 | Listar las etiquetas remotas | `git ls-remote --tags origin` | Aparecen `battery-v1`, `pilot-freeze`, `final-freeze` y `entrega-2` | | |
| 6.2 | `battery-v1` existe | — | Sí. Es lo que el artículo cita como evidencia del preregistro | | |
| 6.3 | `pilot-freeze` existe | — | Sí | | |
| 6.4 | El código congelado no se movió | `git diff final-freeze -- src config prompts data` | **Salida vacía** | | |

## 7. Conclusión de la revisora

**¿El repositorio es reproducible desde cero?** _(sí / no / con reparos)_

_(Escribe aquí tu valoración. Si algo no funcionó, indica en qué paso y con qué
mensaje de error.)_

**Firma:** _(nombre y fecha)_
