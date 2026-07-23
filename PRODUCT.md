# La Queta — Product Document

## Goal
**La Queta** is a free, public web app for learning Catalan through leveled lessons and vocab practice (A1 → A2). Progress is saved per user so learners can return across sessions.

## Principles
- **Free to use, free to run.** No paid SaaS; host on an Oracle Always Free VM.
- **Levels first.** Content and progress are organised by CEFR level, not by ad-hoc decks alone.
- **Start at A1/A2.** B1/B2 only if interest justifies the content work.
- **Prototype is reference only.** UX and content patterns live in `prototype/`; do not extend that app.

---

## Scope

### In scope (v2)
- Public web app (no install)
- Handle-only identity + cookie session (not security-hardened auth)
- Levels: A1 open; A2 and B1 hub tiles exist but disabled (“coming soon”) until content ships.
- Lessons with text / rule / examples / exercises
- Vocab study (seen-count retirement: 3 views)
- Level hub: start or switch levels; completeness per level
- SQLite persistence for users, content, and progress
- Deploy on Oracle Always Free VM

### Out of scope (for now)
- A2 / B1 / B2 **content** (hub shows A2/B1 as coming soon)
- OAuth, email magic links, password-reset email
- Spaced repetition (SM-2)
- Audio / pronunciation playback
- Mobile native apps
- Paid hosting or multi-instance scaling
- Adding cards/lessons via admin UI (seed/migrate instead)

---

## User identity
- **Name** (stored as `handle`), **email**, and **password** — required to create an account.
- Email shape checked with regex only — **no verification mail** in v2.
- Passwords hashed (Werkzeug); never stored or returned in plaintext.
- Sign in with email + password on any device; session cookie after login (~1 year).
- No OAuth / magic links yet.
- Purpose: cross-device progress with a simple account.

---

## Learning flow

```
Home
  → Level hub (A1 | A2) with % complete
    → Level home
         → Lessons (ordered list, completion state)
         → Vocab decks for that level
```

- Default path: continue current level / next incomplete lesson.
- User may start A2 without finishing A1; progress per level is independent.
- Lesson complete when Practice finishes with all items correct (Learn \| Practice tabs; see `PHASE_9_A1_PRACTICE.md`).
- Learners can **Retire** early from study or browse (`seen = max(seen, 3)`). When a deck is fully retired, **Unretire deck** resets all seen counts to 0 so Study is available again.

---

## Level completeness
Shown on the level hub as a single % per level, derived from:
- Lesson completion ratio (primary)
- Optional: vocab retirement ratio (secondary; weight defined in technical plan)

Do not invent a third progress system.

---

## Features

### Phase A — Foundation
- [x] App skeleton at repo root (Flask + Poetry + pytest) — Phase 0
- [x] SQLite + Alembic models/migrations — Phase 1
- [x] Simple email + password auth (no OAuth / no email verify)
- [x] Level hub (A1, A2) with empty/seeded progress

### Phase B — Content & Learn
- [x] Seed A1 lessons from `prototype/` (all → A1; A2 scaffold empty)
- [x] Lesson list + lesson page (sections + multiple-choice)
- [x] Lesson progress persisted per user

### Phase C — Vocab
- [x] Decks scoped to a level
- [x] Study + browse modes (patterns from prototype UI)
- [x] Per-user seen counts

### Phase D — Polish & ship
- [x] Multi-page UX (gate → levels → level → lesson/deck)
- [x] Continue / switch level UX
- [x] Deploy to Oracle Always Free VM — live; see `DEPLOY.md`
- [x] Backup story for SQLite file (on-VM cron; optional Mac pull)

### Phase E — Vocab UX
- [x] Study keyboard: **Enter** (and Next) advance + increment `seen`; **Space** / card click flips
- [x] Browse: retired badge / muted row when `seen >= 3`
- [x] **Retire now** on study + browse (`POST /api/cards/<id>/retire`)
- [x] **Unretire deck** when all cards retired (`POST /api/decks/<slug>/unretire`)
- [ ] Later: **Daily vocab** — sample from level’s unretired pool
- [ ] Later (optional): browse filter active vs retired

### Phase F — A1 Practice ✅
See **`PHASE_9_A1_PRACTICE.md`**. Learn \| Practice tabs; MC + cloze + type-in; complete only after perfect Practice.

### Phase G — A1 path (in progress)
See **`PHASE_10_A1_PATH.md`**. Can-dos + daily vocab shipped; coverage matrix; more lessons/vocab started. Listening / LLM speaking deferred.

**Still out of scope:** SM-2 / difficulty ratings; audio playback; OAuth; email verification / magic-link / password reset email.

---

## Content sources
Reuse and re-level material from `prototype/data/` and `prototype/lessons/`. New lessons/decks authored as seed data, not by mutating the prototype app.

**Level assignment (locked):** all current prototype decks and lessons seed into **A1**. **A2** and **B1** exist as hub placeholders (disabled) until content is authored.

## Success criteria
- A stranger can open the URL, create an account, start A1, complete a lesson, study vocab, sign in later on another device and see progress.
- Operator cost: **$0**/month within Oracle Always Free limits.
