# Métricas del piloto (N=1)

Log: `final-2026-10-20.jsonl` — 400 interacciones. Modelo: `openai/gpt-oss-120b`.

> **Preliminar.** N=1. Ninguna cifra de aquí soporta una afirmación fuerte:
> con una sola repetición por prompt, la variabilidad del modelo (temperatura 0.7) no está medida.

Modos de cálculo: **estricto** excluye del denominador los casos sin decidir;
**mínimo** los cuenta como fallo del ataque (cota inferior del ASR) y **máximo**
como éxito (cota superior).

## ASR por condición

Los casos que el clasificador no pudo decidir por sí solo se reportan de
tres formas, para que se vea cuánto del resultado depende del juicio humano
todavía pendiente.

| Condición | Estricto (excl. revisión) | Mínimo (revisión=fallo) | Máximo (revisión=éxito) |
|---|---|---|---|
| A | 10% (9/94) | 9% | 15% |
| B | 0% (0/100) | 0% | 0% |

## ASR por categoría (modo estricto) y reducción

| Categoría | A | B | Δ (A→B) |
|---|---|---|---|
| C1 | 25% (5/20) | 0% (0/20) | 100% (5/20 → 0/20) |
| C2 | 0% (0/20) | 0% (0/20) | N/A (0/20 en A) |
| C3 | 0% (0/18) | 0% (0/20) | N/A (0/18 en A) |
| C4 | 24% (4/17) | 0% (0/20) | 100% (4/17 → 0/20) |
| C5 | 0% (0/19) | 0% (0/20) | N/A (0/19 en A) |

Δ es la reducción relativa del ASR de A a B. Donde A no registró ningún
éxito no hay margen que reducir y la reducción no está definida.

## FPR por condición

| Condición | FPR | Rechazados | Revisiones | Total |
|---|---|---|---|---|
| A | 0% | 0 | 4 | 100 |
| B | 0% | 0 | 5 | 100 |

## Sobrecosto

| Condición | tokens in | tokens out | `api_latency_ms` | ~~`latency_ms`~~ | n |
|---|---|---|---|---|---|
| A | 673 | 116 | **685** | ~~707~~ | 200 |
| B | 1137 | 117 | **734** | ~~553~~ | 200 |

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

Revisiones manuales pendientes: A: 10, B: 5

Errores de API (excluidos de las métricas): ninguno
