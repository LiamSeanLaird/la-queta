# Phase 10 — A1 path (coverage + daily vocab)

**Status:** first slice shipped (more content iterations continue)  
**Goal:** Close the biggest A1 gaps we can without media/LLM: **theme coverage**, **can-dos**, **daily vocab retention**.  
**Related:** `PHASE_9_A1_PRACTICE.md` (shipped), `PRODUCT.md`, `TECHNICAL_PLAN.md`.

Snapshot at lock: **6** lessons, **7** decks, **~189** cards. Target direction: Generalitat A1 programme themes + CPNL-style situations.

---

## Locked decisions

| # | Topic | Choice |
|---|---|---|
| 1 | Phase 10 scope | Coverage matrix + can-dos UI + **daily vocab** + **first content fill** (new lessons/decks). Listening / LLM speaking stay deferred (Phase 11+). |
| 2 | Curriculum north star | Generalitat A1 programme themes; no mythical official word dump. Track coverage in `content/a1_coverage.md`. |
| 3 | Can-dos | `content/a1_can_dos.json` → shown on A1 level Learn tab; **done** when all linked `lesson_ids` are completed. |
| 4 | Daily vocab | `GET /api/levels/<id>/daily` → up to **20** cards from level: prefer unretired, fill from retired (soft reintroduce). UI `/levels/<id>/daily` reuses study flip flow. Seen++ still applies. |
| 5 | Content fill this phase | Add **≥3** new A1 lessons with practice banks + **≥40** new vocab cards across highest-gap themes (identity, food/café, directions). Expand existing decks where possible. |
| 6 | Completeness formula | Unchanged (0.7 lessons + 0.3 vocab). Can-dos are guidance, not a third progress system. |

---

## Build checklist

- [x] Decisions locked  
- [x] `content/a1_coverage.md` matrix  
- [x] `content/a1_can_dos.json` + level page UI  
- [x] Daily vocab API + page + tests  
- [x] New lessons (≥3) + practice  
- [x] New/expanded vocab (≥40 cards)  
- [x] Docs / rules / TECHNICAL_PLAN  

---

## Deferred (superseded)

Listening/speaking browser slice → **`PHASE_11_LISTENING_SPEAKING.md`**. Remaining: hosted audio, LLM speaking, lemma push, SM-2, A2.

---

## Decision log

| Date | Note |
|---|---|
| 2026-07-23 | Listening + LLM speaking deferred; no official fixed A1 word list |
| 2026-07-23 | Phase 10 locked: matrix + can-dos + daily vocab + first content fill |
