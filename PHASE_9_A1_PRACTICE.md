# Phase 9 — A1 Practice (teach → drill)

**Status:** shipped  
**Scope:** A1 only. Move La Queta from “grammar scroll + recognition vocab” toward **controlled production** that can actually support an A1 path.  
**Out of this phase:** audio/listening, speaking, SM-2, daily vocab / spacing, A2 content, can-do exam simulator.

Related docs: `PRODUCT.md`, `TECHNICAL_PLAN.md`, `STYLE_GUIDE.md`.

---

## Locked decisions

| # | Topic | Choice |
|---|---|---|
| 1 | Complete gate | **Practice-only.** Teach has no Mark complete. Lesson completes when Practice finishes with all items correct. |
| 2 | Inline MCs | **Move into Practice.** Teach = `text` / `rule` / `examples` only. |
| 3 | Type-in matching | **Normalize** trim + collapse whitespace + case-fold; **accents must match** (Catalan orthography is the learning target). Accept any entry in `answers[]` after normalize. |
| 4 | Content slice | **All 6 A1 lessons** this phase: migrate existing MCs + add cloze/type-in so each bank is usable end-to-end. |
| 5 | Daily vocab / spacing | **Defer to Phase 10.** |
| 6 | UX shape | **Learn \| Practice tabs** on the same lesson URL (`?tab=learn` \| `?tab=practice`), same pattern as level Learn/Vocab. Easy switch without losing place in the lesson. |

---

## Why this phase

| Need | Today | This phase |
|---|---|---|
| Teach grammar | 6 lessons (OK scaffold) | Cleaner teach surface (no exercises in scroll) |
| Practice volume | Few MCs in the scroll | Dedicated Practice tab + larger bank |
| Retrieval / production | Recognition + MC only | **Cloze + type-in** (+ MC) |
| Durable vocab | Seen×3 then gone | Deferred (Phase 10) |
| Listening | None | Deferred |

---

## Product behaviour (target)

```
Level Learn list
  → Lesson URL
       → tab Learn: text / rule / examples
       → tab Practice: sequenced drills
            → all correct → POST complete → redirect to level Learn list
```

- Default tab: `learn`. Deep link: `/lessons/<id>?tab=practice`.
- Progress / Continue / completeness % still key off **lesson completed**.
- Vocab decks unchanged.
- Already-completed lessons: Practice stays available for review; completing again is idempotent (already done).
- If Practice bank is empty (shouldn’t happen after seed): do not allow complete; surface a clear empty state.

### Exercise kinds (v1)

| Kind | Prompt | Learner action | Pass rule |
|---|---|---|---|
| `multiple_choice` | `question` + `options` | tap option | equals `answer` |
| `cloze` | `prompt` with `___` (+ optional `hint`) | type blank (default); if `options` present → MC cloze | normalized match to `answer` / `answers[]` |
| `type_in` | English/gloss `prompt` | type Catalan | normalized match to `answers[]` (or single `answer`) |

### Practice UX details

- **One item at a time** (mobile focus).
- Wrong → show `explanation`, stay on item until correct, then advance.
- Progress meta on Practice tab (e.g. `3 / 10`).
- Finish → complete API → redirect `/levels/<level_id>` (Learn tab).
- Tab switch mid-practice: allowed; client may keep in-memory answers for the session (no server draft state in v1).

### Content shape (seed JSON)

```json
{
  "id": "noun-gender",
  "title": "Noun Gender",
  "order": 1,
  "summary": "…",
  "sections": [ /* text | rule | examples only */ ],
  "practice": [
    {
      "id": "ng-p01",
      "kind": "multiple_choice",
      "question": "…",
      "options": ["…"],
      "answer": "…",
      "explanation": "…"
    },
    {
      "id": "ng-p02",
      "kind": "cloze",
      "prompt": "___ porta",
      "hint": "the door",
      "answer": "la",
      "explanation": "…"
    },
    {
      "id": "ng-p03",
      "kind": "type_in",
      "prompt": "the table",
      "answers": ["la taula"],
      "explanation": "…"
    }
  ]
}
```

- Seed upsert loads `practice` → `practice_json` on the lesson row.
- Seed **strips** any leftover `type: exercise` from `sections` if present (content files should be cleaned).
- **Minimum bank:** ≥ 8 items per lesson, with ≥ 2 cloze and ≥ 2 type-in where the topic supports it (MC migrated counts toward the 8).

### Matching (shared helper)

```
normalize(s) = lowercase(trim(collapse_internal_whitespace(s)))
# do NOT strip diacritics
match(user, accepted) = normalize(user) in { normalize(a) for a in accepted }
```

---

## Technical approach

### Data / API

1. Alembic: add `lessons.practice_json` (JSON, default `[]`).
2. Seed: write `practice_json`; sections without exercises.
3. `GET /api/lessons/<id>` — include `practice` array (answers included; no anti-cheat in v1).
4. `POST /api/lessons/<id>/complete` — require `exercises_correct == exercises_total == len(practice)` when practice non-empty (keep payload field names for compat, or alias `practice_*`; prefer keeping `exercises_*` unless tests make rename cheap).
5. Reject incomplete / mismatched totals with 400.

### Pages / UI

| URL | Job |
|---|---|
| `/lessons/<id>` | Lesson shell with **Learn \| Practice** tabs |
| `/lessons/<id>?tab=practice` | Same page, Practice active |

- Reuse `.tab-bar` / `.tab-btn` from level hub.
- Learn panel: existing section renderer minus exercises; no complete button.
- Practice panel: driven by `static/js/practice.js` (or lesson.js extended — prefer dedicated `practice.js` included on lesson page).
- Style guide: document Learn/Practice tab usage + type-in field in the same change.

### Completeness / Continue

- No change to completeness weights.
- Continue → next incomplete lesson; after practice-complete, list shows Done.

---

## Implementation order

1. **Failing tests** — `practice_json` present after migrate/seed; GET includes practice; sections have no exercises; complete rejects imperfect score / wrong total; lesson HTML has Learn/Practice tabs; Learn has no Mark complete.
2. **Structure** — model + migration; tabbed lesson template stubs; matching helper module/util.
3. **Behaviour** — seed all 6 lessons; practice UI; complete + redirect.
4. **Green tests**.
5. **Docs** — this file checklist; `PRODUCT.md`; `TECHNICAL_PLAN.md`; `STYLE_GUIDE.md`; `.cursor/rules/frontend.mdc` (+ python if needed).

---

## Explicit non-goals (Phase 9)

- Audio / TTS / listening  
- Speaking / recording  
- SM-2 or interval scheduling  
- Daily vocab pool (**Phase 10**)  
- A2 lessons  
- CEFR can-do checklist UI  
- Anti-cheat (hiding answers)  
- Separate `/practice` URL (tabs instead)

---

## Phase 10 candidates

1. Daily vocab from level unretired (+ light reintroduction of recently retired).  
2. Listening discrimination once media policy allows.  
3. A1 can-do checklist mapped to lessons/decks.  
4. More A1 dialogue / high-frequency chunk content.

---

## Checklist

- [x] Decisions 1–6 locked  
- [x] Migration `practice_json`  
- [x] Seed + content for all 6 A1 lessons (MC moved + cloze/type-in)  
- [x] Lesson Learn \| Practice tabs + practice JS  
- [x] Teach trimmed (no exercises, no Mark complete)  
- [x] Complete API gate aligned to practice length  
- [x] Tests green  
- [x] Docs / rules updated  

---

## Decision log

| Date | Decision | Choice |
|---|---|---|
| 2026-07-23 | Phase goal | Teach/Practice split + cloze/type-in for A1 |
| 2026-07-23 | Q1 Complete gate | Practice-only completes lesson |
| 2026-07-23 | Q2 Inline MCs | Move to Practice; Teach content-only |
| 2026-07-23 | Q3 Matching | Normalize case/space; accents required |
| 2026-07-23 | Q4 Content | All 6 A1 lessons this phase |
| 2026-07-23 | Q5 Daily vocab | Phase 10 |
| 2026-07-23 | Q6 UX | Learn \| Practice tabs on `/lessons/<id>` |
