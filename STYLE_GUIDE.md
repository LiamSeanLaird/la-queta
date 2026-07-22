# Style Guide — La Queta

Living conventions for humans and AI. Cursor enforces the same via `.cursor/rules/`.
If code and this doc diverge, update both in the same change.

**Product:** La Queta (`la-queta`). **Language taught:** Catalan (vocab field `catalan` stays — that is content, not the brand).

## Live component gallery

Open **`/style-guide`** while the app is running:

```bash
poetry run flask --app wsgi run -p 5001
# → http://127.0.0.1:5001/style-guide
```

That page renders every shared UI component (tokens, brand, type, buttons, forms, tabs, progress, level tiles, list rows, flashcard, exercise options, examples table, seen dots).

- **Markup + classes:** `templates/style_guide.html`
- **Shared styles:** `static/app.css` (gallery chrome uses `.sg-*`; app components do not)
- When you add a UI pattern to the app, **add it to the gallery in the same change**.


---

## 1. Product & process

- **Source of truth:** `PRODUCT.md` (what), `TECHNICAL_PLAN.md` (how), this file (how it should look/feel in code).
- **Do not edit `prototype/`.** Read-only reference for UX patterns and seed content.
- **Phases:** failing tests → structure → behaviour → green tests → docs/rules if needed.
- **One vertical slice per session.** Do not half-migrate JSON and SQLite in the same PR-sized chunk without a clear cutover.
- **No drive-by refactors.** Touch only what the phase needs.

---

## 2. Python

### Layout
- App factory in `app/__init__.py` (`create_app`).
- Routes = blueprints under `app/routes/`.
- Domain logic in `app/services/` (not in route handlers).
- Models only in `app/models.py` until splitting is justified.

### Style
- Python 3.12+: use modern typing (`list[str]`, `X | None`).
- Prefer explicit names over cleverness.
- No comments that narrate what code does; comment only non-obvious intent.
- Keep route handlers thin: validate → service → return JSON/template.

### ORM (SQLAlchemy 2)
- Use 2.0 style only: `Mapped[]`, `mapped_column`, `select()` / `db.session.execute`. No legacy `Query` API (`Model.query`, `.get()`).
- Models are the schema source of truth. Declare FKs/uniques/relationships on the model.
- `db.session` via Flask-SQLAlchemy. **Commit in the service** (or a helper the service owns), not in the route.
- JSON columns (`sections_json`, `tags_json`): opaque at the ORM edge; validate/shape in services.
- API/services return plain dicts (or simple structures) for JSON — do not serialize live ORM instances from routes (avoids lazy-load / detached-instance surprises).
- Enforce uniqueness in the DB (`UNIQUE`). Catch `IntegrityError` → map to HTTP `409`.
- Prefer explicit `select(...)` with the columns/entities you need; no “fetch everything then filter in Python” for list endpoints.

### Migrations (Alembic / Flask-Migrate)
- Schema changes **only** via Alembic. Never hand-edit a production/dev DB schema.
- Enable **batch mode** for SQLite in `migrations/env.py`.
- Workflow: change models → `flask db migrate -m "…"` → **read the revision** → `flask db upgrade` → tests.
- One concern per revision (add table / add column / backfill). Autogenerate is a draft, not gospel.
- Migration message: imperative, present tense (`add user_card_progress`).
- Do not edit revisions that have already been applied anywhere shared; write a new revision instead.
- **Data ≠ schema:** lesson/vocab/content seeds go through `scripts/seed.py` (idempotent). Migrations do not insert content rows (empty `levels` rows OK if useful).
- Tests: in-memory SQLite; prefer running migrations (or the project’s chosen Testing setup) rather than a one-off schema that drifts from Alembic.

### Testing
- `pytest` + Flask test client.
- Prefer behaviour tests (HTTP / service) over testing SQLAlchemy internals.
- Use in-memory SQLite in tests (`Testing` config).
- Name tests `test_<behaviour>`.
- Mutating API endpoints: at least one happy path + one unauthenticated (`401`) case.

### Dependencies
- Poetry only. Dev tools in `[tool.poetry.group.dev.dependencies]`.
- Do not `poetry add` a package already constrained in `pyproject.toml` to a different major without updating the existing pin first.

---

## 3. API

### Surface
- Prefix JSON APIs with `/api/`.
- Resource URLs use stable ids/slugs from the DB (`/api/lessons/<id>`, `/api/decks/<slug>`).
- No `/v1` versioning until we have external API consumers.
- Pages (HTML) stay outside `/api/`; JSON APIs do not return HTML.

### Layers
- Route: parse/validate input, require session if needed, call service, return `jsonify` + status.
- Service: business rules, queries, commits.
- No OpenAPI/Marshmallow/pydantic required — validate with small explicit checks (`if not handle: …`).

### Auth
- Cookie session (`session_user` / Flask session). Missing or invalid session on protected routes → `401` `{ "error": "…" }`.
- Register/claim handle: conflict on duplicate → `409`.
- Unauthenticated browsers hitting HTML progress pages redirect to the handle gate (not a JSON 401).

### HTTP & bodies
- Allowed statuses: `200`, `201`, `204`, `400`, `401`, `404`, `409`, `422`. Don’t invent others without updating this list.
- Success body: resource or list as-is (no `{ "data": … }` wrapper).
- Error body: always `{ "error": "<stable message>" }`. No stack traces, no SQL text.
- Request/response keys: `snake_case`, aligned with model field names where practical.
- Nest at most one level unless the plan already defines a blob (`sections`).
- Mutations: `POST` for create and actions (`/complete`, `/seen`, `/select`). Skip `PUT`/`PATCH` until partial updates are real requirements.
- `GET` is read-only (no “GET that increments seen”).

### Out of scope (for now)
- API versioning, repository pattern, soft deletes, cursor pagination frameworks, schema-codegen.

---

## 4. Frontend (HTML / CSS / JS)

### Stack rules
- Flask templates + vanilla CSS/JS only.
- **No** React, Vue, Next, Tailwind, Bootstrap, HTMX, Alpine — unless PRODUCT/TECHNICAL_PLAN explicitly change.
- One shell template is fine early; split when a file becomes hard to navigate (~800+ lines of mixed concerns).
- JS in `static/app.js` (split later by screen if needed). CSS in `static/app.css`.
- No build step, no bundler.

### HTML
- Semantic structure (`main`, `nav`, `section`, `button` for actions).
- Accessible labels on interactive controls.
- Catalan UI chrome can mix EN labels for learners; content language follows lesson/card data.

### CSS
- Design tokens as CSS variables on `:root` (see Visual design).
- Mobile-first; usable at 360px width.
- Prefer layout via flex/grid; avoid absolute positioning for primary flow.
- **No cards by default** — card chrome only when it frames an interaction (flashcard flip, exercise choice).
- No purple/indigo gradient themes, no glow stacks, no emoji as UI.
- Avoid generic AI defaults: Inter/Roboto/Arial system stacks as the brand voice; purple-on-white; cool limestone + teal; newspaper broadsheet layouts.

### JS
- Small, explicit functions; no framework patterns.
- Talk to the backend via `fetch` + JSON.
- Progressive enhancement where cheap; study/lesson flows may require JS (acceptable).

---

## 5. Visual design

Intentional **La Queta** look — Catalan learning tool with Senyera **red + gold** as the primary colour language (gold-washed surface, red CTAs, gold progress/highlights). Not teal-limestone, not a marketing landing page, not café-terracotta pastiche.

### Brand signals
- Product name **La Queta** is the primary identity on the home/hub (not the word “Catalan” alone).
- Tagline may reference Catalan / Català (e.g. “aprèn català”).
- Senyera colours: gold `#FCCC12`, red `#C1001F` — used as **system accents** (brand title, primary buttons, progress, selection), not as a flag wallpaper.
- **No** `.senyera-bar` / flag strip at the top of screens.

### Tokens
```css
:root {
  --bg: #f7f1df;            /* gold-washed surface */
  --bg-elevated: #fffdf6;
  --ink: #1c1412;
  --muted: #6e5a48;
  --accent: #c1001f;        /* senyera red — primary actions */
  --accent-hover: #9e0019;
  --senyera-gold: #FCCC12;
  --senyera-red: #C1001F;
  --highlight: #FCCC12;     /* progress / filled accents */
  --danger: #9f1239;
  --ok: #15803d;
  --border: #e5d4a0;
  --track: #efe2b4;
  --tab-rail: #f0e6c4;
  --surface-solid: #ffffff;
  --radius: 10px;
  --font-ui: "Figtree", "Segoe UI", sans-serif;
  --font-display: "Fraunces", Georgia, serif;
}
```

### Colour roles
- **Red (`--accent` / `--senyera-red`):** brand title, primary buttons, links, current borders.
- **Gold (`--senyera-gold` / `--highlight`):** progress fill, seen dots, rule-callout accent, current-tile inset.
- **Surface:** soft gold wash + optional top radial wash in `body` background — atmosphere without flag chrome.

### Typography
- **Fraunces** (display) for brand, level titles, lesson headings.
- **Figtree** (sans) for UI chrome, buttons, exercises, body.
- Load fonts via Google Fonts **or** system stack fallbacks if offline; do not block app on fonts.

### Motion
- 2–3 intentional motions max (e.g. card flip, progress bar fill, screen fade).
- Prefer `transform` / `opacity`; keep durations ≤ 250ms for UI chrome.

### Screens (IA)
1. Handle gate  
2. Level hub (A1 / A2 + %)  
3. Level home (lessons + decks)  
4. Lesson  
5. Vocab study / browse  

One job per screen. No dashboard soup.

---

## 6. Content & data

- Runtime source of truth: **SQLite**.
- Authoring/seed: `content/` JSON → `scripts/seed.py` (idempotent).
- Levels in v2: **A1 and A2 only**.
- Lesson section types stay aligned with prototype: `text`, `rule`, `examples`, `exercise`.
- Vocab retirement: `seen >= 3` per user/card.

---

## 7. Git & hygiene

- Do not commit `.venv/`, `*.db`, `.env`, secrets.
- Commit when asked; message focuses on why.
- No `--no-verify` unless explicitly requested.

---

## Changelog
| Date | Change |
|---|---|
| 2026-07-22 | Initial style guide (post Phase 0, pre Phase 1) |
| 2026-07-22 | Rebrand to La Queta (`la-queta`) |
| 2026-07-22 | Live component gallery at `/style-guide` |
| 2026-07-22 | Visual SoT: Senyera red + gold (Fraunces/Figtree); no flag bar |
| 2026-07-22 | API / ORM / migration conventions expanded in §2–3 |
