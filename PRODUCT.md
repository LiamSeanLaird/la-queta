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
- Levels: **A1** and **A2**
- Lessons with text / rule / examples / exercises
- Vocab study (seen-count retirement: 3 views)
- Level hub: start or switch levels; completeness per level
- SQLite persistence for users, content, and progress
- Deploy on Oracle Always Free VM

### Out of scope (for now)
- B1 / B2 content and UI
- Passwords, OAuth, email magic links
- Spaced repetition (SM-2)
- Audio / pronunciation playback
- Mobile native apps
- Paid hosting or multi-instance scaling
- Adding cards/lessons via admin UI (seed/migrate instead)

---

## User identity
- User picks a **handle** (unique, displayable).
- Session stored in an HTTP-only cookie.
- No password. Same browser/device keeps progress; new device = new handle (or later: export — not v2).
- Purpose: save progress, not secure accounts.

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
- Lesson complete when all exercises answered (score stored; no forced re-test).
- Vocab: each card shown until `seen >= 3`, then **retired for that user** — excluded from study sessions; still visible in browse (with seen dots). Early retire (mark known) and daily unretired practice are planned next, not shipped yet.

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
- [x] Handle signup / cookie session
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

### Phase E — Vocab UX (planned; not started)
Study/browse polish after Phase D deploy can ship in parallel if desired:

- [ ] Study keyboard: **Enter** (and Next button) advance + increment `seen`; **Space** (or card click) flips. Match prototype muscle memory.
- [ ] Browse: make retirement obvious (e.g. “Retired” badge / muted row when `seen >= 3`), not only three filled dots.
- [ ] **Retire now** control on study + browse — set that user’s card to retired without waiting for three passive views (still `seen = 3` under the hood unless we introduce an explicit flag later).
- [ ] Later: **Daily vocab** — small random session from the level’s unretired pool (not one deck only); natural “Continue” surface. Keep out of SM-2 territory.
- [ ] Later (optional): un-retire / reset seen for a card; filter browse active vs retired.

**Still out of scope:** SM-2 / difficulty ratings; audio playback.

---

## Content sources
Reuse and re-level material from `prototype/data/` and `prototype/lessons/`. New lessons/decks authored as seed data, not by mutating the prototype app.

**Level assignment (locked):** all current prototype decks and lessons seed into **A1**. **A2** exists as an empty scaffold (level row + hub tile) until content is authored.

## Success criteria
- A stranger can open the URL, pick a handle, start A1, complete a lesson, study vocab, return later and see progress.
- Operator cost: **$0**/month within Oracle Always Free limits.
