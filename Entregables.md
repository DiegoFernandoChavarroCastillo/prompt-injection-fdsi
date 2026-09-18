# Entregables — Entrega intermedia

**Diseño y Evaluación de Mecanismos de Defensa contra Inyección Directa de
Instrucciones en Asistentes Virtuales**

Fundamentos de Seguridad de la Información · Escuela Colombiana de Ingeniería
Julio Garavito · Septiembre de 2026

Laura Alejandra Venegas Piraban · David Palacios · Diego Fernando Chavarro

---

## Resumen del avance

Se construyeron y se pusieron a funcionar los dos asistentes que el estudio
compara: una línea base sin defensas de aplicación y una versión protegida con
cinco capas. Están completos la batería de 20 ataques y los 20 prompts benignos,
el ejecutor automatizado, el clasificador de resultados y el cálculo de métricas,
con 183 pruebas automáticas. Se ejecutó una **corrida piloto de 80 interacciones
sin errores**, cuyo resultado preliminar es una tasa de éxito de los ataques del
**15 % contra la línea base y del 0 % contra la versión protegida**, sin que
ningún prompt legítimo quedara bloqueado en ninguna de las dos. Ese resultado es
**preliminar**: procede de una sola repetición por prompt (N=1) y no permite
distinguir un comportamiento estable de una variación puntual del modelo.

---

## Guía de lectura

Recomendamos revisar el material en este orden:

1. **El artículo** (`main.tex`) — el trabajo en sí. La Sección IV trae los
   resultados del piloto, marcados como preliminares.
2. **Este documento** — qué se entregó y dónde está cada cosa.
3. **Los resultados del piloto** (`results/pilot/`) — las cifras, los casos que
   necesitaron revisión humana y las observaciones descriptivas.
4. **El registro de decisiones** (`docs/DECISIONES.md`) — por qué cada decisión
   metodológica se tomó así y qué alternativa se descartó. Es lo que permite
   juzgar si el experimento está bien montado.
5. **El código** (`src/`) — solo si se quiere verificar la implementación.

---

## Entregables

### Artículo

| Ruta | Qué es |
|---|---|
| `main.tex` | Artículo completo en LaTeX. El resumen (*abstract*) sigue pendiente a propósito: se escribe al final, cuando existan los resultados definitivos |
| `docs/anexo_A.tex` | Anexo A generado: los 20 ataques y los 20 benignos con sus metadatos |
| `docs/anexo_B.tex` | Anexo B generado: los prompts de ambas condiciones y el diff que prueba su simetría |
| `docs/seccion_IV_piloto.tex` | Subsección de resultados preliminares, incluida en la Sección IV |
| `docs/verificar_en_overleaf.md` | Puntos a comprobar al compilar; no se pudo compilar LaTeX en la máquina de desarrollo |

*No se incluye PDF: el artículo debe compilarse en Overleaf.*

### Código

| Ruta | Qué hace |
|---|---|
| `src/config.py` | Carga y valida la configuración del experimento; la deja inmutable |
| `src/prompts.py` | Carga los prompts y acota qué secciones vigila la capa L5 |
| `src/battery.py` | Carga la batería y verifica que no haya cambiado desde que se congeló |
| `src/llm_client.py` | Único punto de contacto con la API del modelo; aplica siempre los mismos parámetros |
| `src/chatbot_a.py` | Condición A: línea base sin defensas de aplicación |
| `src/chatbot_b.py` | Condición B: orquesta las cinco capas de defensa |
| `src/defenses/l3_input_filter.py` | Capa L3: filtro de entrada (normalización, decodificación y reglas) |
| `src/defenses/l5_output_validator.py` | Capa L5: validación de la salida (canary, delimitadores, n-gramas, marcadores) |
| `src/runner.py` | Ejecuta la batería contra ambas condiciones y registra cada interacción |
| `src/classifier.py` | Etiqueta cada interacción según el árbol de decisión del artículo |
| `src/metrics.py` | Calcula ASR, FPR y sobrecosto |
| `scripts/smoke_test.py` | Comprueba que la conexión con el modelo funciona |
| `scripts/try_chatbot.py` | Prueba manual de un chatbot con un prompt suelto |
| `scripts/freeze_battery.py` | Congela la batería y verifica su integridad |
| `scripts/calibrate_l5.py` | Calibra el umbral de L5 usando solo prompts benignos |
| `scripts/report_pilot.py` | Clasifica el log del piloto y genera los tres informes |
| `scripts/export_annex_a.py`, `export_annex_b.py` | Generan los anexos del artículo desde los datos |
| `scripts/prompt_report.py` | Compara los prompts de A y B y muestra el diff |

### Datos

| Ruta | Qué contiene |
|---|---|
| `data/attacks_v1.json` | Los 20 ataques, cuatro por cada una de las cinco categorías |
| `data/benign_v1.json` | Los 20 prompts legítimos: 15 ordinarios y 5 difíciles |
| `data/MANIFEST.txt` | Huellas SHA-256 que prueban que la batería no cambió desde que se congeló |
| `data/dev_attacks.json` | 25 ataques y 15 benignos **de desarrollo**, usados para construir las defensas sin mirar la batería real |
| `data/classifier_markers.json` | Marcadores que permiten decidir automáticamente si un ataque tuvo éxito |

### Prompts

| Ruta | Qué es |
|---|---|
| `prompts/system_A.txt` | Instrucciones del asistente en la condición A |
| `prompts/system_B.txt` | Las mismas, más los bloques de defensa |
| `prompts/l2_reminder.txt` | Recordatorio que se reinyecta después del mensaje del cliente |
| `prompts/messages.yaml` | Mensajes de rechazo, idénticos para que el usuario no sepa qué capa actuó |
| `prompts/canary.txt` | Secreto sintético cuya aparición delata una fuga |

### Resultados del piloto

| Ruta | Qué contiene |
|---|---|
| `results/pilot/metricas.md` | ASR, reducción por categoría, FPR y sobrecosto |
| `results/pilot/observaciones.md` | Qué capa actuó en cada bloqueo y qué señales de alerta se activaron |
| `results/pilot/revision_manual.csv` | Los dos casos que el clasificador no pudo decidir solo, ya revisados a mano |
| `logs/pilot/pilot-2026-09-18.jsonl` | Registro crudo: las 80 interacciones completas |
| `logs/pilot/pilot-2026-09-18_classified.jsonl` | El mismo registro con las etiquetas añadidas |

### Evidencia y documentación del proceso

| Ruta | Qué documenta |
|---|---|
| `docs/DECISIONES.md` | Las 14 decisiones metodológicas, con fecha, alternativa descartada y evidencia |
| `docs/proceso/incidencias.md` | Los dos incidentes detectados y cómo se resolvieron |
| `docs/proceso/bitacora_sesion_autonoma.md` | Diario de la sesión de trabajo autónomo |
| `docs/proceso/instrucciones_sesion_autonoma.md` | El encargo que se le dio a la herramienta, sin retoques |
| `docs/evidencia/` | Salidas crudas de las verificaciones, con un índice que explica qué demuestra cada una |
| `docs/cambios_pendientes_main.md` | Los cambios propuestos al artículo y su justificación |

### Pruebas automáticas

**183 pruebas, todas en verde.** No consumen cuota de la API: los componentes que
hablan con el modelo se sustituyen por dobles.

| Archivo | Nº | Qué cubre |
|---|---|---|
| `tests/test_chatbot_b.py` | 30 | Estructura del contexto de la condición B y orquestación de las capas |
| `tests/test_llm_client.py` | 26 | Parámetros congelados, reintentos y medición de latencia |
| `tests/test_l3.py` | 20 | Que el filtro no bloquee prompts legítimos y sí detecte ataques |
| `tests/test_l5.py` | 18 | Detección de fugas y, sobre todo, que no bloquee respuestas correctas |
| `tests/test_classifier_metrics.py` | 18 | Clasificación de resultados y cálculo de métricas |
| `tests/test_prompts.py` | 16 | Simetría entre los prompts de A y B |
| `tests/test_battery.py` | 16 | Integridad de la batería y su preregistro |
| `tests/test_chatbot_a.py` | 14 | Que la condición A sea fielmente la del artículo |
| `tests/test_config.py` | 12 | Que los parámetros del experimento no cambien |
| `tests/test_antisesgo.py` | 9 | Que las defensas no se construyeran mirando la batería |
| `tests/test_dev_set_independence.py` | 4 | Que el conjunto de desarrollo no se parezca a la batería |

---

## Trazabilidad

Tres etiquetas de git marcan estados del repositorio que se pueden verificar.

| Etiqueta | Commit | Qué garantiza |
|---|---|---|
| `battery-v1` | `b5e83d2` | La batería quedó fijada **antes** de escribir una sola línea de las defensas. Sus huellas SHA-256 están en `data/MANIFEST.txt` y las pruebas las comprueban en cada ejecución |
| `pilot-freeze` | `cbce3dd` | Estado exacto del código con el que se ejecutó el piloto. Los resultados de la Sección IV son reproducibles sobre esta versión |
| `final-freeze` | `afd49bd` | Estado sobre el que se ejecutará la corrida definitiva. Incluye la corrección del defecto de medición de latencia |
| `entrega-2` | *(este commit)* | Estado del repositorio en el momento de esta entrega |

---

## Cómo verificar

Todo lo siguiente funciona **sin consumir cuota de la API**.

```bash
git clone https://github.com/DiegoFernandoChavarroCastillo/prompt-injection-fdsi
cd prompt-injection-fdsi
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 1. Las 183 pruebas
pytest

# 2. El ejecutor, con respuestas simuladas y solo prompts legítimos
python -m src.runner --dry-run --n 1 --condition both --set benign

# 3. Recalcular todas las métricas del piloto desde los registros guardados
python scripts/report_pilot.py logs/pilot/pilot-2026-09-18.jsonl
```

El tercer comando regenera `results/pilot/metricas.md` a partir del registro
crudo: las cifras del artículo se pueden reproducir sin volver a llamar al modelo.

Para ejecutar el experimento de verdad hace falta una clave de API
(`cp .env.example .env` y completarla).

---

## Pendientes para la entrega final

- [ ] **Corrida definitiva N=5** (400 interacciones) sobre la etiqueta `final-freeze`.
- [ ] **Auditoría manual independiente**: el 25 % de los casos, estratificado por
      categoría y condición, más **todos** los éxitos parciales, revisados por
      **dos personas por separado**, con el índice κ de Cohen como medida de
      concordancia.
- [ ] **Sección IV definitiva** con los resultados de N=5.
- [ ] **Sección V (Discusión)**: contraste con la Tabla 4 (matriz de cobertura
      defensa-amenaza), análisis por capa usando `raw_model_output` y
      `defense_trace`, y limitaciones.
- [ ] **Sección VI (Conclusiones)**.
- [ ] **Resumen (*abstract*)**, que se escribe al final.
- [ ] **Revisión cruzada** de la batería de ataques y del filtro L3 por los
      integrantes que no los escribieron.
- [ ] *(Opcional)* **Estudio de ablación por capas**, para poder atribuir el
      efecto a cada una. El piloto no lo permite: L3 intercepta antes de que las
      demás actúen.
- [ ] **Presentación final** y guion de demostración (borrador en
      `docs/guion_demo.md`).

---

## Distribución del trabajo

**En esta entrega intermedia**, la implementación la realizó **Diego Fernando
Chavarro** con asistencia de Claude Code (Anthropic) como herramienta de
programación, según se declara en el artículo. El diseño experimental y las
decisiones metodológicas están documentados en `docs/DECISIONES.md` para que el
equipo pueda revisarlos.

**Reparto propuesto para la entrega final:**

| Integrante | Responsabilidad |
|---|---|
| **Laura Alejandra Venegas Piraban** | Auditoría manual independiente (revisora 1) · Revisión cruzada de la batería de ataques · Redacción de la Sección V |
| **David Palacios** | Auditoría manual independiente (revisora/revisor 2) · Revisión cruzada del filtro L3 · Cálculo del κ de Cohen y Sección VI |
| **Diego Fernando Chavarro** | Ejecución de la corrida definitiva · Métricas y figuras · Integración del artículo y resumen |

La auditoría manual y la revisión cruzada se asignan deliberadamente a Laura y
David: **ninguno de los dos escribió la batería ni el filtro**, y esa distancia es
justamente lo que hace válida la revisión. Que quien construyó una defensa juzgue
si funciona es el sesgo que el resto del montaje se ha esforzado en evitar. Por el
mismo motivo la auditoría la hacen dos personas por separado y se mide la
concordancia entre ellas: sin κ de Cohen, las etiquetas subjetivas no son
defendibles.
