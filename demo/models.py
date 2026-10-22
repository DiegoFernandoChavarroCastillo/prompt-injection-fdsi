"""Modelos de Groq que se pueden elegir en la demo.

Solo la demo los usa: el experimento sigue congelado en ``openai/gpt-oss-120b``
(``config/experiment.yaml``). Cambiar de modelo aquí sirve para enseñar cómo
se comporta un modelo más débil con y sin PromptX, no produce datos.

Disponibilidad comprobada con ``GET /openai/v1/models`` de Groq el 2026-10-21.
De esa lista solo quedan los modelos de chat: los ``whisper-*`` y ``orpheus-*``
son de audio y ``llama-prompt-guard-*`` son clasificadores de prompts.

Precios en USD por millón de tokens, de https://console.groq.com/docs/models
(misma fecha). ``allam-2-7b`` sigue respondiendo en la API pero Groq ya no lo
lista ni publica su precio: su costo se muestra como desconocido, no se inventa.

``reasoning``: si el modelo acepta ``reasoning_effort``/``include_reasoning``.
Los que no, los rechazan con un 400, así que se quitan de la configuración.

``attack_rate`` es lo que salió del sondeo de 20 ataques x 1 contra la
versión sin protección (``EXITO_TOTAL`` / 20). Es orientativo, no un resultado
del experimento: N=1 y sin revisión manual.
"""

from __future__ import annotations

DEFAULT_MODEL = "openai/gpt-oss-120b"

#: Orden del selector: primero el del experimento, luego de más a menos vulnerable.
MODELS: tuple[dict, ...] = (
    {
        "id": "openai/gpt-oss-120b",
        "label": "GPT-OSS 120B",
        "note": "el del experimento",
        "price_in": 0.15, "price_out": 0.60,
        "reasoning": True,
        "attack_rate": None,  # su cifra es la de la corrida definitiva: 9 a 15 de 100
    },
    {
        # Sondeo: 7 éxitos, 8 en revisión manual, 5 fallos. Con PromptX, de los
        # 15 que no fallaron sin protección: 10 fallos (8 por L3, 1 por L5),
        # 4 en revisión y 1 éxito (A14); 5 de 5 benignos atendidos.
        "id": "allam-2-7b",
        "label": "ALLaM 2 7B",
        "note": "el más vulnerable",
        "price_in": None, "price_out": None,
        "reasoning": False,
        "attack_rate": 7 / 20,
    },
    {
        "id": "openai/gpt-oss-20b",
        "label": "GPT-OSS 20B",
        "note": "pequeño",
        "price_in": 0.075, "price_out": 0.30,
        "reasoning": True,
        "attack_rate": 1 / 20,
    },
    {
        "id": "openai/gpt-oss-safeguard-20b",
        "label": "GPT-OSS Safeguard 20B",
        "note": "vista previa",
        "price_in": 0.075, "price_out": 0.30,
        "reasoning": True,
        "attack_rate": 1 / 20,
    },
    {
        "id": "qwen/qwen3.8-27b",
        "label": "Qwen 3.8 27B",
        "note": "vista previa",
        "price_in": 0.80, "price_out": 4.00,
        "reasoning": True,
        "attack_rate": 0 / 20,
    },
)

MODEL_IDS: tuple[str, ...] = tuple(m["id"] for m in MODELS)


def get_model(model_id: str) -> dict | None:
    return next((m for m in MODELS if m["id"] == model_id), None)
