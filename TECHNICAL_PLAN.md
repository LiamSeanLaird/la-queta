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
  sort_order
  sections_json  -- teach sections: text | rule | examples
  practice_json  -- practice bank: multiple_choice | cloze | type_in

decks
  id PK
  level_id FK
  slug UNIQUE
  title
  sort_order

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
  seen INT DEFAULT 0
  UNIQUE(user_id, card_id)
```

Level completeness (derived, not stored):
```
lesson_ratio = completed_lessons / total_lessons_in_level
vocab_ratio  = retired_cards (seen >= 3) / total_cards_in_level
complete_pct = round(100 * (0.7 * lesson_ratio + 0.3 * vocab_ratio))
```
If a level has zero vocab, use lessons only (100% weight).

## Auth / session
- `POST /api/auth/register` `{ "handle", "email", "password" }` → `201` + session cookie
- `POST /api/auth/login` `{ "email", "password" }` → `200` + session (generic `401` on failure)
- `POST /api/auth/logout` → `204`
- Email: regex shape check only (no confirmation email). Password: min 6 chars; Werkzeug hash.
- Cookie: Flask session; HTTP-only; `SameSite=Lax`; `SECRET_KEY`-signed; permanent ~1 year
- Name (`handle`): 2–40 chars, unique case-insensitive. Email unique lowercased.
- Unauthenticated API → 401; pages redirect to gate
- No OAuth / magic links / password-reset mail in v2

## API (initial)

Conventions: `STYLE_GUIDE.md` §3 (layers, statuses, error shape, POST-for-actions).

| Method | Route | Description |
|---|---|---|
| GET | `/` | App shell |
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
| GET | `/api/decks/<slug>/cards` | All cards + seen |
| GET | `/api/decks/<slug>/session` | Unretired cards, shuffled |
| POST | `/api/cards/<id>/seen` | Increment seen |
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

### Phase 7 — Deploy
- [x] First production path on OCI Always Free (gunicorn + nginx + systemd + SQLite) — details in `DEPLOY.md`
- [x] Public HTTP (NSG TCP 80 + host iptables TCP 80 + `/api/health`)
- [x] GitHub read-only deploy key on VM (`github.com-la-queta` remote)
- [x] Daily SQLite backup cron (`DEPLOY.md`)
- [x] `scripts/deploy.sh` / `make deploy` + `deploy/` unit & nginx templates
- [ ] CI SSH deploy (optional later)
- [ ] HTTPS / domain (optional later)

### Phase 8 — Vocab UX ✅
- [x] Study: Enter → Next (seen++); Space / click → flip
- [x] Browse: retired badge / muted row; Retire per row
- [x] Study Retire → `POST /api/cards/<id>/retire` then advance
- [x] Deck fully retired → Unretire deck (`POST /api/decks/<slug>/unretire`)
- [ ] Later: daily practice across level unretired pool
- [ ] Later (optional): browse filter active vs retired

### Phase 9 — A1 Practice ✅
See **`PHASE_9_A1_PRACTICE.md`**. Learn \| Practice tabs; cloze + type-in; practice-only complete; daily vocab deferred to Phase 10.
- [x] Lock open questions in the phase plan
- [x] `practice_json` + seed (all 6 A1 lessons)
- [x] Lesson Learn \| Practice tabs + drill UI
- [x] Complete gate + docs

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
