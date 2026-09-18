# Métricas del piloto (N=1)

Log: `pilot-2026-09-18.jsonl` — 80 interacciones. Modelo: `openai/gpt-oss-120b`.

> **Preliminar.** N=1. Ninguna cifra de aquí soporta una afirmación fuerte:
> con una sola repetición por prompt, la variabilidad del modelo (temperatura 0.7) no está medida.

Modos de cálculo: **estricto** excluye del denominador los casos sin decidir;
**mínimo** los cuenta como fallo del ataque (cota inferior del ASR) y **máximo**
como éxito (cota superior).

## ASR por condición

**No queda ningún caso pendiente de revisión**: los dos que lo estaban se
revisaron a mano. Por eso los tres modos de cálculo coinciden; se conservan
en la tabla para dejar constancia de que el resultado no depende de cómo se
traten los casos ambiguos.

| Condición | Estricto (excl. revisión) | Mínimo (revisión=fallo) | Máximo (revisión=éxito) |
|---|---|---|---|
| A | 15% (3/20) | 15% | 15% |
| B | 0% (0/20) | 0% | 0% |

## ASR por categoría (modo estricto) y reducción

| Categoría | A | B | Δ (A→B) |
|---|---|---|---|
| C1 | 25% (1/4) | 0% (0/4) | 100% (1/4 → 0/4) |
| C2 | 0% (0/4) | 0% (0/4) | N/A (0/4 en A) |
| C3 | 25% (1/4) | 0% (0/4) | 100% (1/4 → 0/4) |
| C4 | 25% (1/4) | 0% (0/4) | 100% (1/4 → 0/4) |
| C5 | 0% (0/4) | 0% (0/4) | N/A (0/4 en A) |

Δ es la reducción relativa del ASR de A a B. Donde A no registró ningún
éxito no hay margen que reducir y la reducción no está definida.

## FPR por condición

| Condición | FPR | Rechazados | Revisiones | Total |
|---|---|---|---|---|
| A | 0% | 0 | 0 | 20 |
| B | 0% | 0 | 0 | 20 |

## Sobrecosto

| Condición | tokens in | tokens out | `api_latency_ms` | ~~`latency_ms`~~ | n |
|---|---|---|---|---|---|
| A | 673 | 129 | **879** | ~~12577~~ | 40 |
| B | 1137 | 124 | **978** | ~~9733~~ | 40 |

> ⚠️ **`latency_ms` de este piloto NO es interpretable.** La columna está tachada
> a propósito. En la corrida del piloto, esa cifra incluía la pausa de 12 s que el
> ejecutor mantiene entre llamadas para respetar los límites del proveedor, porque
> el espaciado se aplicaba dentro de la interacción y no entre interacciones. El
> efecto además es desigual: las interacciones que L3 bloquea no llaman a la API y
> no esperaban, así que la condición B aparece como más rápida que la A, lo cual es
> absurdo.
>
> **La cifra válida de latencia es `api_latency_ms`**, que mide solo la llamada al
> modelo. El sobrecosto en tokens no está afectado. El defecto se corrigió después
> del piloto (ver [`docs/proceso/incidencias.md`](../../docs/proceso/incidencias.md),
> entrada B-02) y la corrida definitiva medirá bien las dos cifras.

Revisiones manuales pendientes: ninguna

Errores de API (excluidos de las métricas): ninguno
