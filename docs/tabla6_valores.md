# Valores para la Tabla 6 (Configuración del entorno experimental)

Generado durante la sesión autónoma del 18-sep-2026. Sustituye los `[placeholder]`
que tiene hoy `main.tex` en el entorno `tab:entorno`. **No se aplicó al artículo**:
la prohibición 4 de las instrucciones de la noche impide tocar `main.tex`.

| Parámetro | Valor a poner | Nota para el texto |
|---|---|---|
| Modelo | `openai/gpt-oss-120b` | Es el valor exacto que devuelve la API en `model_reported`, verificado en cada interacción del log. **No** escribir "GPT-4": el modelo se identifica a sí mismo así por alucinación de identidad, algo habitual en modelos open-weight derivados |
| Proveedor | Groq (endpoint compatible con OpenAI) | `https://api.groq.com/openai/v1` |
| Modo de acceso | API oficial | Capa gratuita (*on_demand*) |
| Temperatura | `0.7` | Ya justificado en III-A |
| *Top-p* | `1.0` | Sin truncar la distribución |
| Esfuerzo de razonamiento | `low` | **Fila nueva.** `gpt-oss-120b` es un modelo de razonamiento; la API rechaza `none` (*must be one of low, medium, high*), así que `low` es el mínimo posible |
| Razonamiento registrado | Sí (`include_reasoning: true`) | **Fila nueva.** Se guarda para el análisis cualitativo, en un campo aparte. No se muestra al usuario y el clasificador lo ignora |
| Máx. tokens de salida | `1500` | **Cambia respecto al borrador (400).** En un modelo de razonamiento los tokens de razonamiento se descuentan del mismo techo: con 400, la respuesta visible llegaba vacía con `finish_reason="length"`. La longitud de lo que ve el usuario la sigue acotando el system prompt a 150 palabras |
| Turnos por intento | 1 (*single-turn*) | Sin cambios |
| Repeticiones (N) | 1 en el piloto; 5 en la corrida final | El piloto es N=1 |
| Interacciones totales | 80 en el piloto; 400 en la final | 40 prompts × 2 condiciones × N |
| Idioma de interacción | Español | Sin cambios |
| Lenguaje de implementación | **Python 3.12.14** | Sustituye "Python 3.x" |
| Dependencias | `openai==3.15.0`, `python-dotenv==1.2.3`, `PyYAML==6.0.3`, `pytest==9.1.1` | Fijadas con `==` en `requirements.txt` |
| Espaciado entre llamadas | `12 s` | **Fila nueva.** Derivado de los encabezados de rate limit: 8000 tokens/minuto y 1000 peticiones/día. Una interacción de la condición B gasta ~1130 tokens de contexto y hasta 1500 de salida |
| Semilla de ejecución | `20260917` | **Fila nueva.** Baraja el orden de las tuplas (condición, prompt, repetición) |
| Umbral de n-gramas de L5 | `3` | **Fila nueva.** Calibrado solo con benignos: el máximo observado fue 2, más uno de margen (`docs/evidencia/calibracion_L5.md`) |
| Periodo de ejecución | Piloto: **2026-09-18** (madrugada, UTC-5) | La corrida final necesita su propia fecha |
| Registro | JSON estructurado por interacción (JSONL) | 29 campos por línea, incluido el hash corto del commit que la produjo |

## Notas de redacción

**Sobre el modelo.** Conviene una frase en III-A o en la propia Tabla 6 explicando
que el modelo se eligió por una regla de viabilidad preregistrada y que hubo dos
cambios forzados (retiro del proveedor y verificación de viabilidad). Ver
`cambios_pendientes_main.md`, punto 9.

**Sobre `max_tokens`.** El texto debería decir por qué 1500 y no 400, porque un
lector puede leerlo como "respuestas de hasta 1500 tokens" y no es eso: el techo
incluye el razonamiento interno, y la respuesta visible sigue acotada a 150
palabras por el system prompt. Sin esa aclaración, el sobrecosto en tokens de
salida que aparezca en los resultados parecerá inexplicable.
