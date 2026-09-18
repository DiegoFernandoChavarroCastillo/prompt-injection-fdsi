# Métricas del piloto (N=1)

Log: `pilot-2026-09-18.jsonl` — 80 interacciones. Modelo: `openai/gpt-oss-120b`.

> **Preliminar.** N=1. Ninguna cifra de aquí soporta una afirmación fuerte:
> con una sola repetición por prompt, la variabilidad del modelo (temperatura 0.7) no está medida.

Los `REVISION_MANUAL` se reportan de tres formas, para que se vea cuánto
depende el resultado del juicio humano todavía pendiente:

- **Estricto**: se excluyen del denominador.
- **Mínimo**: todos cuentan como fallo del ataque (cota inferior del ASR).
- **Máximo**: todos cuentan como éxito (cota superior del ASR).
## ASR por condición

| Condición | Estricto (excl. revisión) | Mínimo (revisión=fallo) | Máximo (revisión=éxito) |
|---|---|---|---|
| A | 11% (2/19) | 10% | 15% |
| B | 0% (0/20) | 0% | 0% |

## ASR por categoría (modo estricto) y Δ

| Categoría | A | B | Δ (A→B) |
|---|---|---|---|
| C1 | 25% | 0% | 100% |
| C2 | 0% | 0% | N/A |
| C3 | 0% | 0% | N/A |
| C4 | 25% | 0% | 100% |
| C5 | 0% | 0% | N/A |

## FPR por condición

| Condición | FPR estricto | Rechazados | Revisiones | Total |
|---|---|---|---|---|
| A | 0% | 0 | 0 | 20 |
| B | 0% | 0 | 1 | 20 |

## Sobrecosto

| Condición | tokens in | tokens out | latency_ms | api_latency_ms | n |
|---|---|---|---|---|---|
| A | 673 | 129 | 12577 | 879 | 40 |
| B | 1137 | 124 | 9733 | 978 | 40 |

Revisiones manuales pendientes: {'A': 1, 'B': 1}
Errores de API (excluidos de las métricas): ninguno
