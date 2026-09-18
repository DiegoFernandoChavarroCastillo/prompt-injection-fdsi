# Contraste del artículo con los datos del piloto

**Revisor:** David Palacios
**Fecha de la revisión:** _(por completar)_
**Versión del artículo revisada:** _(commit o fecha del PDF)_

---

## Para qué sirve esta revisión

Comprobar, cifra por cifra, que **lo que dice el artículo es lo que dicen los
datos**. Es la revisión que detecta el error más caro y más difícil de ver: un
número correcto en el análisis que se transcribe mal al texto, o una afirmación
que ya no corresponde a la tabla que la respalda.

Las fuentes contra las que hay que contrastar son:

- `results/pilot/metricas.md` — las métricas calculadas.
- `logs/pilot/pilot-2026-09-18_classified.jsonl` — el registro crudo clasificado.
- `data/` y `prompts/` — para los anexos.

**Rellena las dos últimas columnas.** Si una cifra no coincide, anota la del
artículo y la de los datos. Ninguna casilla debe quedar vacía.

---

## 1. Tabla 6 — Configuración del entorno experimental

| # | Dato del artículo | Contrastar con | ¿Coincide? (sí/no) | Observaciones |
|---|---|---|---|---|
| 1.1 | Modelo `openai/gpt-oss-120b` | campo `model_reported` en el log | | |
| 1.2 | Temperatura 0,7 | `config/experiment.yaml` y campo `params` del log | | |
| 1.3 | Top-p 1,0 | ídem | | |
| 1.4 | Máx. tokens de salida 1500 | ídem | | |
| 1.5 | Esfuerzo de razonamiento `low` | ídem | | |
| 1.6 | Interacciones del piloto: 80 | número de líneas del log | | |
| 1.7 | Espaciado 12 s | `config/experiment.yaml` | | |
| 1.8 | Semilla 20260917 | campo `execution_seed` del log | | |
| 1.9 | Umbral de n-gramas de L5: 3 | `config/experiment.yaml` | | |
| 1.10 | Python 3.12.14 | `README.md` / `requirements.txt` | | |

## 2. Tabla 7 — ASR por condición

| # | Dato del artículo | Contrastar con | ¿Coincide? | Observaciones |
|---|---|---|---|---|
| 2.1 | ASR condición A: 15 % | `metricas.md`, tabla de ASR por condición | | |
| 2.2 | Éxitos de A: 3/20 | ídem | | |
| 2.3 | ASR condición B: 0 % | ídem | | |
| 2.4 | Éxitos de B: 0/20 | ídem | | |

## 3. Tabla 8 y Figura 5 — ASR por categoría

| # | Dato del artículo | Contrastar con | ¿Coincide? | Observaciones |
|---|---|---|---|---|
| 3.1 | C1: A 25 % (1/4), B 0 % (0/4), Δ 100 % | `metricas.md` | | |
| 3.2 | C2: A 0 % (0/4), B 0 % (0/4), Δ N/A | ídem | | |
| 3.3 | C3: A 25 % (1/4), B 0 % (0/4), Δ 100 % | ídem | | |
| 3.4 | C4: A 25 % (1/4), B 0 % (0/4), Δ 100 % | ídem | | |
| 3.5 | C5: A 0 % (0/4), B 0 % (0/4), Δ N/A | ídem | | |
| 3.6 | La Fig. 5 muestra los mismos valores que la Tabla 8 | comparar figura y tabla | | |
| 3.7 | La leyenda de la Fig. 5 dice «piloto preliminar, $N=1$» | leer la figura | | |

## 4. IV-A.3 — Costo en usabilidad

| # | Dato del artículo | Contrastar con | ¿Coincide? | Observaciones |
|---|---|---|---|---|
| 4.1 | FPR del 0 % en ambas condiciones | `metricas.md`, tabla de FPR | | |
| 4.2 | Ningún prompt benigno bloqueado | campo `blocked_by` de las líneas con `set: benign` | | |
| 4.3 | Los cinco benignos difíciles pasaron | ídem, para B16–B20 | | |

## 5. IV-A.4 — Sobrecosto

| # | Dato del artículo | Contrastar con | ¿Coincide? | Observaciones |
|---|---|---|---|---|
| 5.1 | Tokens de entrada: 673 (A) frente a 1 137 (B) | `metricas.md`, tabla de sobrecosto | | |
| 5.2 | Incremento del 69 % | calcular 1137/673 | | |
| 5.3 | Tokens de salida: 129 (A) y 124 (B) | `metricas.md` | | |
| 5.4 | Latencia de la llamada: 879 ms (A) y 978 ms (B) | columna `api_latency_ms` | | |
| 5.5 | El artículo **no** usa el tiempo total por interacción como sobrecosto | buscar en IV-A.4 | | |

## 6. Resumen (abstract)

| # | Afirmación del resumen | Contrastar con | ¿Coincide? | Observaciones |
|---|---|---|---|---|
| 6.1 | «del 15 % en la línea base al 0 %» | Tabla 7 | | |
| 6.2 | «sin que ninguna consulta legítima resultara bloqueada» | Tabla de FPR | | |
| 6.3 | «80 interacciones» | número de líneas del log | | |
| 6.4 | «la línea base rechazó por sí sola 17 de los 20 ataques» | 20 − 3 éxitos | | |
| 6.5 | Está marcado como «(Versión preliminar.)» | leer el PDF | | |

## 7. Anexos

| # | Comprobación | Cómo | ¿Coincide? | Observaciones |
|---|---|---|---|---|
| 7.1 | El Anexo A contiene los 20 ataques de `data/attacks_v1.json` | comparar identificadores y payloads | | |
| 7.2 | El Anexo A contiene los 20 benignos de `data/benign_v1.json` | ídem | | |
| 7.3 | A20 aparece con su intención decodificada y la nota de ofuscación | leer el anexo | | |
| 7.4 | El Anexo B reproduce `prompts/system_A.txt` exactamente | comparar con el archivo | | |
| 7.5 | El Anexo B reproduce `prompts/system_B.txt` exactamente | ídem | | |
| 7.6 | El Anexo B reproduce `prompts/l2_reminder.txt` exactamente | ídem | | |
| 7.7 | El diff A→B del Anexo B solo muestra adiciones | leer el anexo | | |

## 8. Referencias

| # | Comprobación | ¿Correcta? | Observaciones |
|---|---|---|---|
| 8.1 | Las referencias están numeradas por orden de primera cita | | |
| 8.2 | [1] Geng et al. — es la fuente del «superior al 90 %» citado en II-A y en Limitaciones | | |
| 8.3 | [2] OWASP Top 10 for LLM Applications | | |
| 8.4 | [3] Perez y Ribeiro | | |
| 8.5 | [4] Greshake et al. | | |
| 8.6 | [5]–[8] StruQ, Instruction Hierarchy, Spotlighting, Signed-Prompt | | |
| 8.7 | [9] HackAPrompt · [10] Liu et al. | | |
| 8.8 | [11] Aguilera y Berzal | | |
| 8.9 | [12] Model card de gpt-oss (arXiv:2508.10925) | | |
| 8.10 | Cada cita del texto apunta a la fuente que realmente respalda la afirmación | | |

## 9. Conclusión del revisor

**¿Las cifras del artículo se corresponden con los datos?** _(sí / no / con reparos)_

_(Escribe aquí tu valoración. Enumera cualquier discrepancia con la cifra del
artículo y la de los datos.)_

**Firma:** _(nombre y fecha)_
