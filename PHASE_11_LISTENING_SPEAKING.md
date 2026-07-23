# Phase 11 — Listening & speaking (browser first)

**Status:** first slice shipped  
**Goal:** Close A1 **listening** and light **speaking** gaps without cloud TTS/STT/LLM yet. Real audio files + LLM scoring come later.  
**Related:** `PHASE_10_A1_PATH.md`, `PRODUCT.md`, `TECHNICAL_PLAN.md`.

---

## Locked decisions

| # | Topic | Choice |
|---|---|---|
| 1 | Scope | **Listening practice items** + **speaking self-check** in lesson Practice. No paid APIs this phase. |
| 2 | Playback | Browser **`speechSynthesis`** (prefer `ca-ES` / `ca_ES` voice; fallback any). Optional future `audio_url` field ignored until we host files. |
| 3 | Listening kinds | `listen_choice` (hear → MC) and `listen_type` (hear → type). Field `speak` = Catalan text to utter. |
| 4 | Speaking kind | `speak`: show target + hint; **Play model** (TTS); **I said it** advances (honour system). If Web Speech Recognition is available for Catalan, show optional transcript feedback — never block completion on STT. |
| 5 | LLM / cloud STT | **Deferred** (Phase 12+). Plan hook only. |
| 6 | Content | Add ≥2 listen + ≥1 speak items to each existing A1 lesson practice bank (≥9 lessons). |
| 7 | Study flashcards | Out of this slice (Practice only). |

---

## Practice item shapes

```json
{
  "id": "ng-l01",
  "kind": "listen_choice",
  "speak": "la porta",
  "question": "What did you hear?",
  "options": ["the door", "the table", "the cat"],
  "answer": "the door",
  "explanation": "…"
}
```

```json
{
  "id": "ng-l02",
  "kind": "listen_type",
  "speak": "el gat",
  "prompt": "Type the Catalan you hear",
  "answers": ["el gat"],
  "explanation": "…"
}
```

```json
{
  "id": "ng-s01",
  "kind": "speak",
  "speak": "Gràcies",
  "prompt": "Say this aloud",
  "hint": "Thank you",
  "explanation": "…"
}
```

Matching for `listen_type` / choice: same normalizer as Phase 9 (accents required).

---

## Build checklist

- [x] Decisions locked  
- [x] `static/js/speech.js` TTS (+ optional recognition helper)  
- [x] Practice UI for listen_* / speak  
- [x] Seed listen/speak items into all A1 lessons  
- [x] Tests (kinds present; page assets)  
- [x] Docs / coverage matrix / PRODUCT (browser audio in scope)  

**Status:** first slice shipped  

---

## Phase 12+ parking lot

- Hosted audio clips (`audio_url`) replacing TTS where quality matters  
- Mic → STT → **LLM** coaching  
- Listening on Daily vocab / study cards  
- More lemma push / shopping·family·home lessons  

---

## Decision log

| Date | Note |
|---|---|
| 2026-07-23 | Phase 11: browser TTS listening + speak self-check; LLM deferred |
