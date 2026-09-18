# prompt-injection-fdsi

Laboratorio de inyección directa de instrucciones en LLMs (OWASP LLM01) para la materia
**Fundamentos de Seguridad de la Información**. Compara dos asistentes que resuelven la
**misma** tarea: la **condición A** (baseline vulnerable, sin defensas) y la **condición B**
(protegida con 5 capas: L1 separación de roles, L2 instrucciones defensivas, L3 filtro de
entrada, L4 delimitadores, L5 validación de salida). Ambas se enfrentan a **20 ataques** en
5 categorías y **20 prompts benignos** (15 ordinarios + 5 difíciles), y se reportan **ASR**
(tasa de éxito de los ataques), **FPR** (benignos rechazados de más) y el sobrecosto en
tokens y latencia.

**Equipo:** Laura Alejandra Venegas Piraban · David Palacios · Diego Fernando Chavarro

---

## Instalación

Requiere **Python 3.12** y git. Desde la raíz del repositorio:

```bash
# 1. Clonar
git clone https://github.com/DiegoFernandoChavarroCastillo/prompt-injection-fdsi
cd prompt-injection-fdsi

# 2. Crear el entorno virtual
python3.12 -m venv venv

# 3. Activarlo
source venv/bin/activate          # bash / zsh
# source venv/bin/activate.fish   # fish
# venv\Scripts\activate           # Windows (PowerShell)

# 4. Instalar dependencias (versiones fijadas)
pip install -r requirements.txt

# 5. Configurar la clave de la API
cp .env.example .env
# Abre .env y pega tu clave en LLM_API_KEY=
```

> **Si no tienes Python 3.12** (por ejemplo, tu sistema trae 3.13 o 3.14), la forma más
> corta de obtenerlo sin tocar el Python del sistema es con [uv](https://docs.astral.sh/uv/):
>
> ```bash
> uv python install 3.12
> uv venv --python 3.12 venv
> ```
>
> No uses otra versión "porque funciona": la versión de Python entra en la Tabla 6 del
> artículo y debe ser la misma para todo el equipo.

La clave se obtiene en la consola del proveedor ([Groq](https://console.groq.com/keys)).
`.env` está en `.gitignore`: **nunca** debe subirse al repositorio, y cada integrante usa
su propia clave.

---

## Uso

### Prueba de humo (una llamada real a la API)

Valida la cadena completa `.env` → `config/experiment.yaml` → cliente → proveedor:

```bash
python scripts/smoke_test.py
```

Imprime el texto de la respuesta, `model_reported`, tokens de entrada y salida, y latencia.
Devuelve código de salida 0 si todo funcionó. **`model_reported` es el identificador exacto
del modelo que va en la Tabla 6 del artículo**, no el alias del YAML.

### Pruebas automáticas (no llaman a la API)

```bash
pytest
```

Los tests de L3 y L5 están marcados como `skip` hasta la Fase 4; se activan quitando el
marcador `@pytest.mark.skip`.

---

## Parámetros congelados

Estas son las **variables controladas** del experimento. Viven en `config/experiment.yaml`
y quedaron fijadas en la Fase 0.

| Parámetro | Valor | Por qué |
|---|---|---|
| Proveedor | `groq` (endpoint compatible con OpenAI) | Roles `system`/`user` separados —necesarios para L1— y cuota suficiente para ~500 llamadas |
| `base_url` | `https://api.groq.com/openai/v1` | Plan B: Gemini en `https://generativelanguage.googleapis.com/v1beta/openai/` |
| Modelo | `llama-3.3-70b-versatile` | El identificador exacto se toma de `model_reported` |
| `temperature` | `0.7` | > 0 a propósito: con 0 el modelo sería casi determinista y las repeticiones no medirían variabilidad (Sección III-A) |
| `top_p` | `1.0` | Sin truncar la distribución; toda la variabilidad la controla la temperatura |
| `max_tokens` | `400` | Suficiente para que una fuga del canary sea visible en la respuesta |
| `n_pilot` | `1` | 1 × 40 prompts × 2 condiciones = **80 interacciones** |
| `n_final` | `5` | 5 × 40 prompts × 2 condiciones = **400 interacciones** |
| `execution_seed` | `20260917` | Baraja el orden de ejecución para que un efecto de orden no se confunda con el efecto de la condición |
| Canary | `INTERNAL-KEY-7F3A9B` | Token centinela del system prompt; su aparición en la salida es fuga objetiva |
| Python | `3.12` | Va en la Tabla 6 |
| Dependencias | ver `requirements.txt` (fijadas con `==`) | Un cambio de versión del SDK puede alterar cómo se envían los parámetros |

> ⚠️ **No modificar ninguno de estos valores sin acuerdo del equipo.** Cambiar uno solo
> rompe la comparabilidad entre la condición A y la B, y entre el piloto y la corrida final:
> las diferencias observadas ya no podrían atribuirse a la defensa. Todo cambio acordado debe
> quedar registrado en el artículo y obliga a volver a correr lo afectado.

---

## Estructura del repositorio

```
prompt-injection-fdsi/
├── config/experiment.yaml     # variables controladas del experimento
├── prompts/                   # system prompts de A y B + canary
├── data/                      # batería: 20 ataques + 20 benignos (Anexo A)
├── src/
│   ├── config.py              # carga y valida la configuración (inmutable)
│   ├── llm_client.py          # ÚNICA puerta hacia la API
│   ├── chatbot_a.py           # condición A (vulnerable)
│   ├── chatbot_b.py           # condición B (5 capas)
│   ├── defenses/              # L3 (entrada) y L5 (salida)
│   ├── runner.py              # ejecuta la batería y escribe logs JSONL
│   ├── classifier.py          # etiqueta las interacciones (Fig. 4)
│   └── metrics.py             # ASR, FPR y sobrecosto
├── scripts/smoke_test.py      # una llamada de prueba a la API
├── tests/                     # pruebas que no consumen cuota
├── logs/pilot/                # datos crudos del piloto (no versionados)
└── results/pilot/             # tablas derivadas (no versionadas)
```

Se versiona lo que hace reproducible el estudio (`config/`, `prompts/`, `data/`, `src/`);
no se versionan los datos generados (`logs/`, `results/`) ni los secretos (`.env`).

---

## Estado del proyecto

El plan completo, con criterios de cierre y riesgos, está en [`PlanDeAccion.md`](PlanDeAccion.md).

| Fase | Qué incluye | Estado |
|---|---|---|
| **0 — Decisiones y configuración inicial** | Repo, `.gitignore`, `.env`, configuración congelada, cliente LLM, smoke test | ✅ **Hecha** |
| 1 — Caso de uso y system prompts | `system_A.txt` y `system_B.txt` (políticas P1–P5) | ⬜ Pendiente |
| 2 — Batería de ataques y benignos | 40 prompts con metadatos, congelados como `v1` (Anexo A) | ⬜ Pendiente |
| 3 — Condición A | Chatbot vulnerable (Listing 1) | ⬜ Pendiente |
| 4 — Condición B | Las cinco capas L1–L5, misma firma `respond()` que A | ⬜ Pendiente |
| 5 — Ejecutor y logs | `runner.py`, logs JSONL reprocesables | ⬜ Pendiente |
| 6 — Clasificador y métricas | Árbol de la Fig. 4 + ASR/FPR/sobrecosto | ⬜ Pendiente |
| 7 — Corrida piloto (N=1) | 80 interacciones, revisión manual de casos ambiguos, tag `pilot-freeze` | ⬜ Pendiente |
| 8 — Actualización del artículo | Tabla 6, Anexos A y B, Sección IV marcada como preliminar | ⬜ Pendiente |
| 9 — Preparación de la entrega | README final, guion de demo, empaquetado | ⬜ Pendiente |

### Qué hay hoy en el repositorio

Lo que ya funciona: la configuración (`src/config.py`), el cliente de la API
(`src/llm_client.py`), el smoke test y las pruebas de configuración. Todo lo demás son
**stubs** con su contrato documentado en el docstring y `raise NotImplementedError`: la
firma y el formato de retorno ya están acordados, así que las fases siguientes pueden
avanzar en paralelo sin chocar entre sí.

---

## Ética

Los ataques de este repositorio se ejecutan **solo** contra los dos asistentes del
laboratorio, creados para el estudio. El canary (`INTERNAL-KEY-7F3A9B`) es sintético y no
protege ningún sistema real, por lo que puede publicarse en el artículo. No se prueban
sistemas de terceros ni se usan datos personales.
