# Bitácora — sesión autónoma 18/19-sep-2026

## RESUMEN PARA DIEGO (actualizar al final)

*(en curso — se completa al terminar)*

---

## Decisiones tomadas sin Diego

*(se añaden según aparecen)*

---

## Registro cronológico

### [03:05] Sección 0 — Antes de empezar
- Leídos `PlanDeAccion.md`, `README.md` e `INSTRUCCIONES_NOCHE.md`.
- `pytest`: **117 pasan, 4 se omiten** (los de L3/L5 en skip). Verde de partida.
- Commit de partida: **57f6c84** "fase 4a: condición B — contexto con L1, L2 y L4".
- `git status`: sin cambios en archivos versionados. Sin versionar: `main.tex`
  (prohibido tocarlo), `INSTRUCCIONES_NOCHE.md`, `notas/fase4a_benignos_B.txt`.
- Llamadas a la API gastadas hasta ahora: **0 / 200**.

### [03:15] 3.1 — Contrato de latencia
- `respond()` pasa a **12 claves**: `latency_ms` mide ahora el total de
  `respond()` en A y en B, y `api_latency_ms` la llamada al modelo (`None` si
  L3 bloqueó). `src.RESPONSE_KEYS` actualizado.
- pytest: 119 pasan, 4 se omiten. Commit **dfd47ff**.
- Llamadas API: 0 / 200.

### [03:35] 3.2 — Fase 4b: conjunto de desarrollo y L3
- `data/dev_attacks.json`: 25 ataques (5 por categoría C1–C5) + 15 benignos de
  desarrollo. Los codificados (D21 Base64, D22 ROT13, D23 homóglifos+U+200B) se
  construyeron programáticamente.
- `tests/test_dev_set_independence.py` **detectó 7 colisiones de 5-gramas** con
  la batería en el primer borrador (D02, D04, D06, D13, D15, D16, D22).
  Reescritos esos payloads hasta cero colisiones. El test cumplió exactamente su
  función: yo había visto la batería en sesiones anteriores y se me filtraron
  frases sin darme cuenta.
- L3 implementado: normalización (NFKC, invisibles, homóglifos cirílicos y
  griegos, espaciado), decodificación (Base64 + ROT13) y 8 reglas en 4 familias.

**Resultados de L3 (calibración permitida: solo contra benignos)**

| Conjunto | Resultado |
|---|---|
| 20 benignos de `benign_v1.json` | **0 bloqueados** (0 % FPR en el filtro) |
| 15 benignos de desarrollo | **0 bloqueados** |
| 25 ataques de desarrollo | **14 bloqueados = 56 %** |

Detección por categoría (de 5 cada una): C1 3, C2 3, C3 4, **C4 1**, C5 3.

Observación: C4 (inyección por contexto engañoso) es la categoría que L3 casi no
detecta, y es esperable: documento contaminado, historial falsificado e
instrucción parasitaria son ataques **semánticos**, no léxicos — el texto no
contiene ninguna orden de anulación, solo un contexto falso. Un filtro de
entrada por reglas no puede verlos; le tocan a L1/L2 (delimitación) y a L5
(validación de salida). Es un resultado a reportar, no un defecto a tapar.

No se persiguió el 100 %: el suelo del test está en 40 % a propósito, para que
no empuje a sobreajustar el filtro a su propio conjunto de desarrollo.
- pytest: 143 pasan, 2 se omiten.
- Llamadas API: 0 / 200.
