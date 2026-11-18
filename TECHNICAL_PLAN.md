# La Queta — Technical Plan (v2)

## Decisions (locked)
| Decision | Choice | Reason |
|---|---|---|
| Product / repo | La Queta (`la-queta`) | Public brand + GitHub repo name |
| Codebase | Rewrite at repo root; `prototype/` frozen | Requirements changed; tiny Python surface; AI works better from clean plans |
| Levels | A1 + A2 only | Defer B1/B2 until interest |
| Hosting | Oracle Always Free VM | True $0 always-on VM; SQLite on local disk |
| Identity | Handle + cookie session | Progress only; not security auth |
| DB | SQLite | Single small instance; simple backups |
| Migrations | Alembic (Flask-Migrate) + batch mode | Same workflow as Postgres; SQLite ALTER limits |
| UI | Flask templates + vanilla HTML/CSS/JS | AI-friendly; no build step; matches prototype patterns |
| ORM | SQLAlchemy 2.x | Required for Alembic; models as source of truth |
| Style | `STYLE_GUIDE.md` + `.cursor/rules/` | Shared human/AI conventions before Phase 1 |

## Stack
- Python 3.12+
- Flask
- SQLAlchemy 2 + Flask-SQLAlchemy
- Flask-Migrate (Alembic)
- gunicorn + nginx on Oracle VM
- Poetry for deps
- pytest for tests

## Repo layout
```
la-queta/
├── PRODUCT.md
├── TECHNICAL_PLAN.md
├── STYLE_GUIDE.md
├── prototype/                 # FROZEN reference (UI + seed content). Do not edit.
├── app/
│   ├── __init__.py            # create_app factory
│   ├── config.py
│   ├── models.py
│   ├── auth.py                # email + cookie
│   ├── routes/
│   │   ├── pages.py
│   │   ├── api_levels.py
│   │   ├── api_lessons.py
│   │   └── api_vocab.py
│   └── services/
│       └── progress.py        # completeness calculations
├── migrations/                # Alembic
├── templates/
├── static/
│   ├── app.css
│   └── app.js
├── content/                   # seed JSON (copied/adapted from prototype)
│   ├── levels.json
│   ├── lessons/
│   └── decks/
├── tests/
├── scripts/
│   └── seed.py
├── pyproject.toml
└── wsgi.py
```

## Data model (summary)

```
users
  id PK
  handle UNIQUE NOT NULL       -- display name
  email UNIQUE NOT NULL       -- login id (lowercased; regex only, no verify)
  password_hash NOT NULL
  created_at
  current_level_id FK NULL

levels
  id PK          -- e.g. "a1", "a2"
  code UNIQUE    -- "A1", "A2"
  title
  sort_order

lessons
  id PK
  level_id FK
  slug UNIQUE
  title
  summary
  sort_order     -- lesson JSON `order`; must follow the goal order in content/a1_can_dos.json (the Learn tab), and the file is named NN-<id>.json (tests/test_lesson_order.py)
  sections_json  -- teach sections: text | rule | examples
  practice_json  -- practice bank: multiple_choice | cloze | type_in
  deck_slug      -- matching vocab deck (lesson JSON `deck`), offered when practice ends

decks
  id PK
  level_id FK
  slug UNIQUE    -- from the file name: content/decks/<slug>_deck.json
  title          -- DECK_TITLES in app/services/seed.py; seeding fails if a deck has none
  sort_order     -- rank of the first lesson whose `deck` field names it (deck_order_from_lessons in app/services/seed.py)

cards
  id PK
  deck_id FK
  external_id UNIQUE  -- preserve prototype ids where possible
  catalan
  english
  pronunciation
  hint
  pos
  gender NULL
  plural NULL
  tags_json
  forms_json          -- verb gerund / past participle when present
  grammar_lesson_id FK NULL

user_lesson_progress
  user_id FK
  lesson_id FK
  completed BOOL
  exercises_correct INT
  exercises_total INT
  completed_at NULL
  UNIQUE(user_id, lesson_id)

user_card_progress
  user_id FK
  card_id FK
  seen INT DEFAULT 0            -- "Knew it" grades (views before grading existed); retired at >= 3
  interval_days INT DEFAULT 0   -- spaced repetition: days until next review, 0 = still learning
  due_at NULL                   -- naive UTC; NULL = never studied
  last_reviewed_at NULL         -- naive UTC time of the last self-grade
  UNIQUE(user_id, card_id)

user_daily_sessions            -- one finished daily vocab per learner per local day
  user_id FK
  level_id FK
  local_date DATE              -- learner's date in their browser timezone
  timezone                     -- IANA name the browser sent, or UTC
  completed_at
  UNIQUE(user_id, local_date)
```

Daily vocab "done for today" and the streak come from `user_daily_sessions` (`app/services/daily.py`).
`static/js/study.js` posts to `/api/levels/<id>/daily/complete` with the browser's timezone when a daily session reaches "Session complete".
The reply (`done_today`, `streak`) fills the "✓ Daily vocab done for today · N-day streak" line on that screen, which only the daily page renders.
`/levels` works out "today" in the timezone of the learner's latest finished session.

Spaced repetition (`grade_card` in `app/services/vocab.py`, `POST /api/cards/<id>/grade`):
"Knew it" moves `interval_days` up the ladder 1, 3, 7, 14, 30, 60 days, sets `due_at` that far ahead, and adds 1 to `seen`.
"Not yet" sets `interval_days` to 0 and `due_at` to now, and leaves `seen` alone, so forgetting a word never retires it.
Migration `c9d0e1f2a3b4` carried existing progress over: seen 1 became interval 1, seen 2 became 3, seen 3 or more became 7, and every studied card was made due at once.
`seen` was not changed, so retired cards stayed retired.
In `static/js/study.js`, a flipped card shows "Not yet" and "Knew it" (keys 1 and 2), which post to `/grade`; study no longer posts to `/seen`.
Each card is graded at most once per session, and a "Not yet" card comes back once at the end of the session for practice without a second grade.
Choosing cards: a card is "new" (no row, or `seen` 0 and no `due_at`), "due" (`due_at` has passed, or studied with no `due_at` yet), or "early" (studied, due later).
Deck study plays due cards (oldest due first), then new cards in deck file order, then early cards shuffled.
Daily vocab picks due cards from the whole level first, then new cards from the focus decks, then new cards from the next decks in order, then early cards (soonest due first), then retired cards from the focus decks, and shuffles the 20 it picked.
"Unretire deck" (`unretire_deck`) makes its cards new again: `seen`, `interval_days` and `due_at` are reset.

Level completeness (derived, not stored):
```
lesson_ratio = completed_lessons / total_lessons_in_level
vocab_ratio  = retired_cards (seen >= 3) / total_cards_in_level
complete_pct = round(100 * (0.7 * lesson_ratio + 0.3 * vocab_ratio))
```
If a level has zero vocab, use lessons only (100% weight).
`complete_pct` only sets the width of the progress bar.
The text learners read comes from `level_progress_counts` and `progress_summary` in `app/services/progress.py`, for example "3 of 20 lessons · 89 words learned".
Words count as "learned" once retired; before any are retired, cards seen at least once show as "words started".
Below the bar, the card names the next goal (can-do) and its lesson count, for example "Next goal: Build core grammar - 2 of 5 lessons".
`next_goal` in `app/services/can_dos.py` picks the unfinished goal that holds the lesson Continue would open, so the card and the Continue button agree.
Goals only tick when every lesson in them is done, so a plain "0/7 goals complete" would sit at zero for the learner's first lessons.

## Auth / session
- `POST /api/auth/register` `{ "handle", "email", "password" }` → `201` + session cookie
- `POST /api/auth/login` `{ "email", "password" }` → `200` + session (generic `401` on failure)
- `POST /api/auth/logout` → `204`
- Email: regex shape check only (no confirmation email). Password: min 6 chars; Werkzeug hash.
- Cookie: Flask session; HTTP-only; `SameSite=Lax`; `SECRET_KEY`-signed; permanent ~1 year
- Name (`handle`): 2–40 chars, unique case-insensitive. Email unique lowercased.
- Unauthenticated API → 401; logged-in-only pages redirect to `/signin`, except public pages
- The gate (sign-up and sign-in forms, `templates/auth.html` + `gate.js`) lives at `/signup` and `/signin` (`noindex`; logged in → `/levels`).
  The tabs switch in place and `replaceState` the URL between the two; old `/#signin` links are forwarded to `/signin` by a one-line script on `/`.
- Public pages: `/` is the landing page for logged-out visitors (logged in → `/levels`): the pitch, "Start lesson 1", every A1 lesson grouped by goal (`learn_groups_for_level(None, "a1")`), the goals, and an FAQ.
  It still renders before content is seeded (no lesson list).
- `/lessons/<id>` (Learn and Practice tabs) renders for logged-out visitors.
  Services take `user=None` for this path (`get_lesson`, `list_lessons_for_level`, `lesson_next_steps`): no progress, nothing completed, no vocab deck, no wrap-round to earlier lessons.
  Logged out, Practice never posts the completion; its last step asks the visitor to create an account or sign in instead.
  Carry-over: when a logged-out visitor finishes Practice, `practice.js` stores `{lesson_id, exercises_correct, exercises_total}` in `sessionStorage` (`laqueta.pendingCompletion`, this tab only).
  After register or login succeeds, `gate.js` removes the entry, re-posts it to `POST /api/lessons/<id>/complete` (the same validation as the logged-in path), and lands on `/lessons/<id>?saved=1`, which shows "Saved to your account." when the lesson is complete.
  No redirect target comes from the URL; without a pending entry, or if the POST fails, the gate goes to `/levels`.
- Every lesson's Learn tab ends with a course nav: previous and next lesson in plain course order (`lesson_neighbours`, which ignores progress, so the links are the same for everyone and a crawler can walk the course), plus "All lessons".
  "All lessons" goes to the lesson list on `/` (`/#lessons-title`) when logged out and to `/levels/<level>` when logged in.
- No OAuth / magic links / password-reset mail in v2

## API (initial)

Conventions: `STYLE_GUIDE.md` §3 (layers, statuses, error shape, POST-for-actions).

| Method | Route | Description |
|---|---|---|
| GET | `/` | Public landing page (logged in → `/levels`) |
| GET | `/signup`, `/signin` | Account forms (gate) |
| POST | `/api/auth/register` | Create account (name + email + password) + set cookie |
| POST | `/api/auth/login` | Email + password → session |
| POST | `/api/auth/logout` | Clear session |
| GET | `/api/me` | Current user + current level |
| GET | `/api/levels` | A1/A2 + completeness % |
| POST | `/api/levels/<id>/select` | Set current level |
| GET | `/api/levels/<id>/lessons` | Lessons + completion |
| GET | `/api/lessons/<id>` | Full lesson (sections + practice) |
| POST | `/api/lessons/<id>/complete` | Perfect practice score required; mark complete |
| GET | `/api/levels/<id>/decks` | Decks + stats |
| GET | `/api/levels/<id>/daily` | Up to 20 cards: due reviews first, then new cards from decks the learner has started or whose lesson they completed (the first deck for a new learner), then new cards from the next decks in order, then reviews not due yet, then retired ones |
| GET | `/api/decks/<slug>/cards` | All cards + seen |
| GET | `/api/decks/<slug>/session` | Unretired cards: due reviews (oldest first), then unseen ones in deck file order, then reviews not due yet |
| POST | `/api/cards/<id>/seen` | Increment seen (legacy; study grades instead) |
| POST | `/api/cards/<id>/grade` | Self-grade `{"grade": "knew" \| "not_yet"}`: updates interval, due date and seen |
| POST | `/api/cards/<id>/retire` | Set seen ≥ 3 (early retire) |
| POST | `/api/decks/<slug>/unretire` | Reset seen → 0 for all cards in deck |

## UI approach
- Server-rendered shell from Flask templates
- Vanilla JS for study/lesson interactions (port patterns from `prototype/templates/index.html`)
- One CSS file with CSS variables; no React/Vue/Tailwind required
- Visual SoT: `STYLE_GUIDE.md` §5 + `/style-guide` — Senyera **red + gold** palette (no flag bar); Fraunces / Figtree
- Multi-page Flask templates (not a single-page screen machine): `/` → `/levels` → `/levels/<id>` → `/lessons/<id>` | `/decks/<slug>/(study|browse)`
- Screens: handle gate → level hub → level home → lesson | vocab study/browse

## Migrations
- Flask-Migrate / Alembic is the only schema change path
- Enable **batch mode** for SQLite in `migrations/env.py`
- Never hand-edit production DB schema
- Seed data via `scripts/seed.py` (idempotent), not via migrations, except empty `levels` rows if useful
- Conventions (workflow, one-concern revisions, ORM/API boundaries): `STYLE_GUIDE.md` §2–3

## Hosting (Oracle Always Free)

**Operator runbook:** [`DEPLOY.md`](DEPLOY.md) (inventory, first-time setup, day-2 deploys, NSG/firewall, backlog). Keep that file current when IP/paths change.

Summary:
- Ubuntu VM + systemd gunicorn (`wsgi:app` on `127.0.0.1:8000`) + nginx on `:80`
- SQLite at `/var/lib/la-queta/app.db`; env in `/etc/la-queta/env` (`SECRET_KEY`, `DATABASE_URL`)
- OCI NSG must allow TCP **22** and **80** (else browser timeouts while SSH still works)
- Backup: daily SQLite `.backup` / copy (see `DEPLOY.md`)
- Domain / HTTPS optional later

## Implementation order (AI execution)

Work in vertical slices. Each phase: **failing tests → structure → behaviour → tests green → update docs if needed.**

### Phase 0 — Scaffold ✅
- [x] Poetry project at root; deps; `create_app`
- [x] Empty routes + health check
- [x] pytest wired

### Phase 1 — Schema & migrations ✅
- [x] Models as above
- [x] Initial Alembic migration
- [x] Tests: migrate on empty DB; model constraints

### Phase 2 — Auth ✅
- [x] Register / login / logout (email + password, hashed; no email verify)
- [x] `/api/me`
- [x] Tests for session round-trip + cross-login

### Phase 3 — Levels API + hub UI ✅
- [x] Seed A1/A2
- [x] Completeness helper (even if 0%)
- [x] Level hub screen + select level

### Phase 4 — Lessons ✅
- [x] Seed from prototype lessons (assign A1/A2)
- [x] List + detail + complete APIs
- [x] Lesson UI (section renderer)

### Phase 5 — Vocab ✅
- [x] Seed decks/cards with level FKs
- [x] Session / seen / browse
- [x] Study UI from prototype patterns

### Phase 6 — Progress polish ✅
- [x] Multi-page navigation (gate → levels → level → lesson/deck)
- [x] Completeness % on hub
- [x] Continue CTA (next incomplete lesson, then vocab with remaining)

### Phase 7 — Deploy ✅
- [x] First production path on OCI Always Free (gunicorn + nginx + systemd + SQLite) — details in `DEPLOY.md`
- [x] Public HTTP (NSG TCP 80 + host iptables TCP 80 + `/api/health`)
- [x] HTTPS / domain (`la-queta.com`, certbot)
- [x] GitHub read-only deploy key on VM (`github.com-la-queta` remote)
- [x] Daily SQLite backup cron (`DEPLOY.md`)
- [x] `scripts/deploy.sh` / `make deploy` + `deploy/` unit & nginx templates
- [ ] CI SSH deploy (optional later)

### Phase 8 — Vocab UX ✅
- [x] Study: Enter / Space / click → flip; then Knew it (2) or Not yet (1) grades the card
- [x] Browse: retired badge / muted row; Retire per row
- [x] Study Retire → `POST /api/cards/<id>/retire` then advance
- [x] Deck fully retired → Unretire deck (`POST /api/decks/<slug>/unretire`)
- [x] Daily vocab from the decks the learner has reached (`/levels/<id>/daily`)
- [ ] Later (optional): browse filter active vs retired

### Phase 9 — A1 Practice ✅
Learn \| Practice tabs; cloze + type-in; practice-only complete.
- [x] `practice_json` + seed
- [x] Lesson Learn \| Practice tabs + drill UI
- [x] Complete gate + docs

### Phase 10 — A1 path ✅
- [x] Coverage matrix (`content/a1_coverage.md`) + can-dos (`content/a1_can_dos.json`)
- [x] Goal grouping + unlock dialog on Learn
- [x] Daily vocab API + page
- [x] Programme content fill (**20** A1 lessons)

### Phase 11 — Listening & speaking ✅ (browser first)
Practice kinds `listen_choice` / `listen_type` / `speak` via Web Speech API; LLM/hosted audio later.
- [x] `speech.js` + practice UI
- [x] Seed listen/speak items on A1 lessons
- [x] Tests + docs

## Running (target)
```bash
# Conda env provides Python; Poetry installs app deps into it (virtualenvs.create = false).
conda env update -f environment.yml --prune   # once / when env spec changes
conda activate la-queta
poetry install

make run          # http://127.0.0.1:5001
make test
make seed         # after migrate
make migrate

# Equivalent long forms:
poetry run python -m pytest
poetry run python -m flask --app wsgi run -p 5001
poetry run python -m flask --app wsgi db upgrade
poetry run python scripts/seed.py
```

Do not leave a broken conda env activated (e.g. empty `catalan` husk with no interpreter) — Poetry will error or wipe installs. Use `la-queta` from `environment.yml`.


## Prototype usage rules
- **Read** `prototype/` for UI patterns and content
- **Do not** add features to `prototype/`
- Content copied into `content/` then seeded into SQLite; after seed, SQLite is runtime source of truth
- **Level assignment:** all current prototype lessons + decks → **A1**; **A2** scaffold empty until new content
