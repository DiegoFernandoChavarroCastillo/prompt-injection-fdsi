"""Servidor local de la demo de PromptX para el jurado: chat A/B y costos.

Solo IMPORTA el código del experimento (``src/``); no lo modifica. Las capas se
apagan inyectando dobles por los parámetros ``l3``/``l5`` de
:func:`src.chatbot_b.respond` y, en el caso de L2, con una copia de los prompts
sin recordatorio. L1 y L4 son estructurales (roles separados y bloques de
``system_B.txt``) y están siempre activas en B.

Lo que se prueba aquí NO es dato del experimento y no se escribe en ``logs/``,
por la misma razón que ``scripts/try_chatbot.py``.

Uso (desde la raíz del repositorio):
    venv/bin/python -m uvicorn demo.server:app --port 8000
    # y abrir http://localhost:8000
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from demo.presets import PRESET_IDS, PRESETS
from src import chatbot_a, chatbot_b
from src.battery import load_attacks, load_benign
from src.classifier import classify
from src.config import Config, load_config
from src.llm_client import LLMCallError, LLMClient
from src.prompts import Prompts, load_prompts

logger = logging.getLogger(__name__)

DEMO_DIR = Path(__file__).resolve().parent
STATIC_DIR = DEMO_DIR / "static"
SNAPSHOT_PATH = DEMO_DIR / "data" / "snapshot.json"

#: Precio de gpt-oss-120b en Groq, USD por millón de tokens. Son los mismos que
#: usa Entrega3.md para el costo por conversación.
PRICE_IN_PER_M = 0.15
PRICE_OUT_PER_M = 0.60

#: Lo que ve la interfaz en lugar del canary, para resaltarlo si se filtra.
CANARY_MASK = "⟦CANARY⟧"

MAX_INPUT_CHARS = 4000


# --------------------------------------------------------------------------
# Dobles de capa: dejan pasar todo y lo dicen en la traza.
# --------------------------------------------------------------------------

class _L3Apagada:
    @staticmethod
    def check_input(text: str) -> dict:
        return {"blocked": False, "rule": None, "normalized": text, "decoded": [], "disabled": True}


class _L5Apagada:
    @staticmethod
    def validate_output(text: str, config: Config | None = None) -> dict:
        return {"passed": True, "check": None, "details": {"disabled": True}}


# --------------------------------------------------------------------------
# Estado del servidor
# --------------------------------------------------------------------------

class DemoState:
    """Todo lo que se carga una vez al arrancar."""

    def __init__(self, config: Config, client=None, snapshot_path: Path = SNAPSHOT_PATH):
        self.config = config
        self.prompts: Prompts = load_prompts(config)
        self.canary = config.canary()
        self.snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.battery = {a.id: a for a in load_attacks(config)} | {b.id: b for b in load_benign(config)}
        self.has_key = bool(config.api_key)
        self.offline = not self.has_key
        self._client = client
        self._lock = threading.Lock()

    @property
    def client(self):
        with self._lock:
            if self._client is None:
                self._client = LLMClient(self.config)
            return self._client

    def mask(self, value):
        """Sustituye el canary en cualquier texto que salga hacia el navegador."""
        if isinstance(value, str):
            return value.replace(self.canary, CANARY_MASK)
        if isinstance(value, dict):
            return {k: self.mask(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.mask(v) for v in value]
        return value


# --------------------------------------------------------------------------
# Modelos de la API
# --------------------------------------------------------------------------

class Layers(BaseModel):
    l2: bool = True
    l3: bool = True
    l5: bool = True


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    condition: Literal["A", "B"]
    layers: Layers = Layers()
    preset_id: str | None = None


class CompareRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    layers: Layers = Layers()
    preset_id: str | None = None


class OfflineRequest(BaseModel):
    offline: bool


# --------------------------------------------------------------------------
# Lógica
# --------------------------------------------------------------------------

def _cost(tokens_in: int | None, tokens_out: int | None) -> float:
    return ((tokens_in or 0) * PRICE_IN_PER_M + (tokens_out or 0) * PRICE_OUT_PER_M) / 1_000_000


def _preset_matches(state: DemoState, preset_id: str | None, text: str) -> str | None:
    """Devuelve el id solo si el texto es el del prompt de la batería, sin editar.

    Si el presentador modifica el texto de una tarjeta, ya no es el caso
    grabado: ni se etiqueta con los marcadores de ese prompt ni se cae al
    respaldo, porque la respuesta grabada sería de otro texto.
    """
    if preset_id in PRESET_IDS and state.battery[preset_id].payload.strip() == text.strip():
        return preset_id
    return None


def _label(state: DemoState, preset_id: str | None, result: dict) -> str | None:
    if preset_id is None:
        return None
    interaccion = {
        "status": "ok",
        "set": "attack" if preset_id.startswith("A") else "benign",
        "prompt_id": preset_id,
        "final_response": result["response"],
        "blocked_by": result["blocked_by"],
    }
    return classify(interaccion, state.canary)["label"]


def _recorded(state: DemoState, preset_id: str, condition: str, reason: str) -> dict:
    grabada = state.snapshot["recorded"][preset_id][condition]
    i = grabada["interaction"]
    return {
        "condition": condition,
        "source": "recorded",
        "recorded_reason": reason,
        "recorded_order_index": i["order_index"],
        "recorded_repetition": i["repetition"],
        "recorded_labels": grabada["labels"],
        "recorded_n": grabada["n"],
        "response": i["final_response"],
        "raw_model_output": i["raw_model_output"],
        "blocked_by": i["blocked_by"],
        "sent_context": i["sent_context"],
        "tokens_in": i["tokens_in"],
        "tokens_out": i["tokens_out"],
        "latency_ms": i["latency_ms"],
        "api_latency_ms": i["api_latency_ms"],
        "defense_trace": i["defense_trace"],
        "label": i["label"],
        "cost_usd": _cost(i["tokens_in"], i["tokens_out"]),
        "layers": {"l1": condition == "B", "l2": condition == "B", "l3": condition == "B",
                   "l4": condition == "B", "l5": condition == "B"},
    }


def run_one(state: DemoState, text: str, condition: str, layers: Layers, preset_id: str | None) -> dict:
    preset = _preset_matches(state, preset_id, text)
    # Lo grabado solo representa a B con las cinco capas: con una capa apagada
    # sería mentir sobre lo que se está viendo.
    todas = layers.l2 and layers.l3 and layers.l5

    if state.offline:
        if preset and (condition == "A" or todas):
            return state.mask(_recorded(state, preset, condition, "modo sin conexión"))
        raise HTTPException(503, "Modo sin conexión: solo están disponibles los prompts "
                                 "predefinidos, sin editar y con todas las capas activas.")

    try:
        if condition == "A":
            result = chatbot_a.respond(text, client=state.client, prompts=state.prompts,
                                       config=state.config)
            activas = dict.fromkeys(("l1", "l2", "l3", "l4", "l5"), False)
        else:
            prompts = state.prompts if layers.l2 else dataclasses.replace(state.prompts, l2_reminder="")
            result = chatbot_b.respond(
                text, client=state.client, prompts=prompts, config=state.config,
                l3=None if layers.l3 else _L3Apagada, l5=None if layers.l5 else _L5Apagada,
            )
            activas = {"l1": True, "l2": layers.l2, "l3": layers.l3, "l4": True, "l5": layers.l5}
    except LLMCallError as exc:
        logger.warning("La API falló: %s", exc)
        if preset and (condition == "A" or todas):
            return state.mask(_recorded(state, preset, condition, "la API no respondió"))
        raise HTTPException(502, f"La API no respondió ({exc}). Prueba un prompt predefinido: "
                                 "tienen respuesta grabada.") from exc

    salida = {k: v for k, v in result.items() if k != "reasoning"}
    salida.update({
        "condition": condition,
        "source": "live",
        "label": _label(state, preset, result),
        "cost_usd": _cost(result["tokens_in"], result["tokens_out"]),
        "layers": activas,
    })
    return state.mask(salida)


def _metrics_view(snapshot: dict) -> dict:
    """Las cifras del panel, ya derivadas, para que el navegador no haga cuentas."""
    m = snapshot["metrics"]
    oh = m["overhead"]
    costo_llamada = {c: _cost(oh[c]["tokens_in_medio"], oh[c]["tokens_out_medio"]) for c in ("A", "B")}
    return {
        "run_id": snapshot["run_id"],
        "git_commit": snapshot["git_commit"],
        "model": snapshot["model"],
        "n_total": m["n_total"],
        "asr": {c: m["asr"][c]["global"] for c in ("A", "B")},
        "asr_by_category": {c: m["asr"][c]["por_categoria"] for c in ("A", "B")},
        "categories": m["categorias"],
        "fpr": m["fpr"],
        "overhead": oh,
        "cost_per_call": costo_llamada,
        "pending_reviews": m["revisiones"],
        "errors": m["errores"],
        # Costo medio contando también las conversaciones que L3 cortó sin
        # llamar al modelo: esas no se pagan. Ver build_snapshot.py.
        "effective_cost": {c: _cost(t["tokens_in"], t["tokens_out"])
                           for c, t in snapshot["effective_tokens"].items()},
    }


# --------------------------------------------------------------------------
# Aplicación
# --------------------------------------------------------------------------

def create_app(state: DemoState | None = None) -> FastAPI:
    app = FastAPI(title="Demo — PromptX", docs_url=None, redoc_url=None)
    app.state.demo = state

    def st() -> DemoState:
        if app.state.demo is None:
            app.state.demo = DemoState(load_config(require_api_key=False))
        return app.state.demo

    @app.get("/api/status")
    def status():
        s = st()
        return {"offline": s.offline, "has_key": s.has_key, "model": s.config.model}

    @app.post("/api/offline")
    def set_offline(req: OfflineRequest):
        s = st()
        if not req.offline and not s.has_key:
            raise HTTPException(400, "No hay LLM_API_KEY en .env: solo funciona el modo sin conexión.")
        s.offline = req.offline
        return {"offline": s.offline}

    @app.get("/api/presets")
    def presets():
        s = st()
        salida = []
        for p in PRESETS:
            item = s.battery[p["id"]]
            grabada = s.snapshot["recorded"][p["id"]]
            salida.append({
                **p,
                "payload": item.payload,
                "category": getattr(item, "category", None),
                "category_name": getattr(item, "category_name", None),
                "technique": getattr(item, "technique", None),
                "objective": getattr(item, "objective", None),
                "recorded_labels": {c: grabada[c]["labels"] for c in ("A", "B")},
                # L3 es determinista: la repetición grabada vale por las cinco.
                "recorded_blocked_by": {c: grabada[c]["interaction"]["blocked_by"] for c in ("A", "B")},
            })
        return salida

    @app.get("/api/example")
    def example():
        """El caso con el que abre la página: A03 grabado contra A y contra B."""
        s = st()
        pid = "A03"
        return s.mask({
            "preset_id": pid,
            "text": s.battery[pid].payload,
            "A": _recorded(s, pid, "A", "ejemplo de apertura"),
            "B": _recorded(s, pid, "B", "ejemplo de apertura"),
        })

    @app.post("/api/chat")
    async def chat(req: ChatRequest):
        return await asyncio.to_thread(run_one, st(), req.text, req.condition, req.layers, req.preset_id)

    @app.post("/api/compare")
    async def compare(req: CompareRequest):
        s = st()
        a, b = await asyncio.gather(
            asyncio.to_thread(_safe_run, s, req.text, "A", req.layers, req.preset_id),
            asyncio.to_thread(_safe_run, s, req.text, "B", req.layers, req.preset_id),
        )
        return {"A": a, "B": b}

    @app.get("/api/results")
    def results():
        s = st()
        vista = _metrics_view(s.snapshot)
        vista["category_names"] = {a.category: a.category_name for a in s.battery.values()
                                   if hasattr(a, "category_name")}
        return vista

    @app.get("/api/config")
    def config_view():
        s = st()
        c = s.config
        return s.mask({
            "provider": c.provider,
            "model": c.model,
            "inference": dataclasses.asdict(c.inference),
            "system_A": s.prompts.system_A,
            "system_B": s.prompts.system_B,
            "system_B_added": s.prompts.system_B[len(s.prompts.system_A):],
            "l2_reminder": s.prompts.l2_reminder,
            "rejection": s.prompts.l3_rejection,
            "delimiters": [chatbot_b.OPEN_DELIMITER, chatbot_b.CLOSE_DELIMITER],
        })

    @app.get("/")
    def index():
        return HTMLResponse(_index_html())

    @app.middleware("http")
    async def sin_cache(request: Request, call_next):
        # Sin esto el navegador reutiliza el CSS y el JS de una versión anterior
        # de la demo junto con el HTML nuevo, y la página sale rota.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache"
        return response

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


def _index_html() -> str:
    """``index.html`` con la huella de cada recurso en su URL, para que nunca se mezclen versiones."""
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for nombre in ("styles.css", "app.js"):
        huella = hashlib.sha256((STATIC_DIR / nombre).read_bytes()).hexdigest()[:10]
        html = html.replace(f"/static/{nombre}\"", f"/static/{nombre}?v={huella}\"")
    return html


def _safe_run(state: DemoState, text: str, condition: str, layers: Layers, preset_id: str | None) -> dict:
    """Como :func:`run_one`, pero un fallo de un lado no tumba la comparación."""
    try:
        return run_one(state, text, condition, layers, preset_id)
    except HTTPException as exc:
        return {"condition": condition, "error": exc.detail}


app = create_app()
