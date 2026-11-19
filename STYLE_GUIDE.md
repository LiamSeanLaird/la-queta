# Style Guide - La Queta

Living conventions for humans and AI. Cursor enforces the same via `.cursor/rules/`.
If code and this doc diverge, update both in the same change.

**Product:** La Queta (`la-queta`). **Language taught:** Catalan (vocab field `catalan` stays - that is content, not the brand).

## Live component gallery

Open **`/style-guide`** while the app is running:

```bash
make run
# → http://127.0.0.1:5001/style-guide
```

(`make test`, `make seed`, `make upgrade` also available - see `TECHNICAL_PLAN.md` Running.)

That page renders every shared UI component (tokens, brand, type, buttons, forms, tabs, progress, level tiles, list rows, flashcard, exercise options, examples table, seen dots).

Flashcards / browse rows carry prototype vocab meta on the Catalan side: pronunciation, grammar pills (pos including phrase / gender / plural), verb forms, tags.
On browse rows, everything that wraps (grammar pills, verb forms, tags) sits in the text column; the right-hand column holds only seen dots and Retire, so it never squeezes the text at phone width.

Study flow: first-load tip dialog (Don’t show again); tap or Enter flips Catalan → English, then Knew it or Not yet grades the card and advances (Knew it counts towards retirement, Not yet queues the card again at the end of the session); Back revisits the previous card; Retire confirms once. A finished session stays on the page and shows a 'Session complete' panel: how many cards the learner went through and retired, a primary 'Study again' (hidden when every card in it was retired), 'Next lesson: <Title>' and a link back to the deck or vocab tab. After deck study the next lesson is the deck's own lesson if it is unfinished, else the first unfinished lesson after it; after daily review it is the level's first unfinished lesson. Without Study again, the next lesson (or the exit link when there is none) becomes the primary button. An empty session shows 'Nothing to study' the same way. Deck page shows retired progress bar; when fully retired, Unretire deck replaces Study (POST unretire → seen 0). Below Study and Browse it lists the lessons linked to the deck (lesson `deck` field), in lesson order with Done/Todo badges. Interaction chrome stays off the card - only pedagogical `hint` text appears when present.

Lessons use Learn | Test tabs (the Test tab was called Practice; `?tab=practice` 301-redirects to `?tab=test`). The Test opens on an intro card - the question count, the rule "Get every question right to complete the lesson.", the lesson's "Words in this lesson" list and a primary "Start the test" button - then goes one question at a time (MC / cloze / type-in / listen_* / speak); typed/STT answers normalize case/space, treat curly apostrophes (’) as straight ones, and strip other punctuation but keep accents. Cloze prompts say fill-the-blank-only; wrong typed Check offers Show answer once. Listening uses browser TTS (`speech.js`). Lesson completes only after a perfect Test run. Learn-tab buttons say "Take the test", or "Take the test again" once the lesson is done.
When the Test ends the learner stays on the lesson: a done panel offers the lesson's matching vocab deck (primary, while it has cards left), the next incomplete lesson, and Back to lessons.
The Learn tab ends with a course nav (`.lesson-nav`): previous and next lesson in course order as two list-row cards (stacked at phone width), and an "All lessons" link.
When a learner finishes the last lesson of a level, the Test done panel shows the "You've finished A1" moment (`templates/_finished_level.html`): daily vocab as the next step and an honest "A2 is not here yet" line.
The hub tile shows the same message (`.level-tile__finished`) once every lesson in the level is complete.

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
- API/services return plain dicts (or simple structures) for JSON - do not serialize live ORM instances from routes (avoids lazy-load / detached-instance surprises).
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
- Poetry only for app packages. Dev tools in `[tool.poetry.group.dev.dependencies]`.
- Do not `poetry add` a package already constrained in `pyproject.toml` to a different major without updating the existing pin first.
- **Conda + Poetry:** activate a **valid** env first (`la-queta` via `environment.yml`). `poetry.toml` sets `virtualenvs.create = false` so deps install into that env. A broken/empty activated env (e.g. husk `catalan` with no `python`) makes Poetry fail or recreate empties - fix/recreate the conda env, don't leave it activated.

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
- No OpenAPI/Marshmallow/pydantic required - validate with small explicit checks (`if not handle: …`).

### Auth
- Cookie session (`session_user` = user id in signed Flask session). Missing or invalid session on protected routes → `401` `{ "error": "…" }`.
- Register: `POST /api/auth/register` with name (`handle`) + email + password → `201`.
- Login: `POST /api/auth/login` with email + password → `200`. Bad creds → `401` `"Invalid email or password"`.
- Logout: `POST /api/auth/logout` → `204`.
- Current user: `GET /api/me` → `200`; `PATCH /api/me` with `handle` + `email` → `200` (duplicate → `409`).
- Email: regex shape only (no verification). Password: Werkzeug hash, min 6 chars. Never return hashes.
- Duplicate name/email → `409`.
- Unauthenticated browsers hitting HTML progress pages redirect to the gate (not a JSON 401).

### HTTP & bodies
- Allowed statuses: `200`, `201`, `204`, `400`, `401`, `404`, `409`, `422`. Don’t invent others without updating this list.
- Success body: resource or list as-is (no `{ "data": … }` wrapper).
- Error body: always `{ "error": "<stable message>" }`. No stack traces, no SQL text.
- Request/response keys: `snake_case`, aligned with model field names where practical.
- Nest at most one level unless the plan already defines a blob (`sections`).
- Mutations: `POST` for create and actions (`/complete`, `/seen`, `/retire`, `/select`). `PATCH /api/me` for profile field updates.
- `GET` is read-only (no “GET that increments seen”).

### Out of scope (for now)
- API versioning, repository pattern, soft deletes, cursor pagination frameworks, schema-codegen.

---

## 4. Frontend (HTML / CSS / JS)

### Stack rules
- Flask templates + vanilla CSS/JS only.
- **No** React, Vue, Next, Tailwind, Bootstrap, HTMX, Alpine - unless PRODUCT/TECHNICAL_PLAN explicitly change.
- One shell template is fine early; split when a file becomes hard to navigate (~800+ lines of mixed concerns).
- JS in `static/app.js` (split later by screen if needed). CSS in `static/app.css`.
- No build step, no bundler.

### HTML
- Semantic structure (`main`, `nav`, `section`, `button` for actions).
- Accessible labels on interactive controls.
- Catalan UI chrome can mix EN labels for learners; content language follows lesson/card data.
- Render lesson prose (text, rule and example-note sections) through the `keep_affixes` filter (`app/text_filters.py`).
  It wraps endings such as `-em`, `-er/-re` and `-eix-` in a `.affix` nowrap span, because browsers may break a line straight after the hyphen.
- Exactly one `<h1>` per page: the page's own title (lesson title, deck title, "Your A1 course").
  The brand in the topbar is a `<p class="brand__title">`, never a heading.
  Heading level and look are separate: pick the element for the outline and the `.heading-*` class for the size.
  A page with no visible title (study) gets `<h1 class="visually-hidden">`.
- `<html lang="en">` stays, because the interface is English.
  Mark Catalan text with `lang="ca"` on the element that holds it: example cells, vocab words, plurals and verb forms, the spoken target in the Test, and the `aprèn català` tagline.
  When JS swaps a flashcard between Catalan and English, it sets `lang` to match the side.
  Mixed English and Catalan text (prompts, rules, notes) stays unmarked.
- Logged-in shell (`base.html` topbar): **←** back left (`{% block top_back %}`), brand center, profile + feedback (mailto / `FEEDBACK_EMAIL`) right, side by side in one row (never stacked). Tagline (`aprèn català`) only on the gate.

### CSS
- Design tokens as CSS variables on `:root` (see Visual design).
- Mobile-first; usable at 360px width.
- Prefer layout via flex/grid; avoid absolute positioning for primary flow.
- Wrap a `.progress-meta` label and its `.progress` bar in `.progress-group`, so they stay one tight unit whatever gap the surrounding stack uses.
- **No cards by default** - card chrome only when it frames an interaction (flashcard flip, exercise choice).
- No purple/indigo gradient themes, no glow stacks, no emoji as UI.
- Avoid generic AI defaults: Inter/Roboto/Arial system stacks as the brand voice; purple-on-white; cool limestone + teal; newspaper broadsheet layouts.

### JS
- Small, explicit functions; no framework patterns.
- Talk to the backend via `fetch` + JSON.
- Progressive enhancement where cheap; study/lesson flows may require JS (acceptable).

---

## 5. Visual design

Intentional **La Queta** look - Catalan learning tool with Senyera **red + gold** as the primary colour language (gold-washed surface, red CTAs, gold progress/highlights). Not teal-limestone, not a marketing landing page, not café-terracotta pastiche.

### Brand signals
- Product name **La Queta** is the primary identity on the home/hub (not the word “Catalan” alone).
- Tagline may reference Catalan / Català (e.g. “aprèn català”).
- Senyera colours: gold `#FCCC12`, red `#C1001F` - used as **system accents** (brand title, primary buttons, progress, selection), not as a flag wallpaper.
- **Favicon / bookmark mark:** gold **smiley** (two dots + smile) on senyera red (`static/favicon.svg`, `favicon-32.png`, `favicon.ico`, `apple-touch-icon.png`) - linked from `base.html`. Wordmark stays the in-app brand; full mascot (if any) is separate.
- **Link previews (WhatsApp / iMessage / etc.):** Open Graph + Twitter cards in `base.html`; share image `static/og-image.png` (1200×630): the smiley, **La Queta**, *aprèn català* and "Free Catalan for complete beginners" on senyera red. It is rendered from `scripts/og_image/og-image.html`; edit that file and run `poetry run python scripts/og_image.py` (needs network for Google Fonts), never hand-edit the PNG. Canonical origin via `PUBLIC_BASE_URL` (default `https://la-queta.com`).
- **No** `.senyera-bar` / flag strip at the top of screens.

### Tokens
```css
:root {
  --bg: #f7f1df;            /* gold-washed surface */
  --bg-elevated: #fffdf6;
  --ink: #1c1412;
  --muted: #6e5a48;
  --accent: #c1001f;        /* senyera red - primary actions */
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
  --link: #c1001f;          /* inline link text */
  --on-accent: #ffffff;     /* text on red buttons */
  --gold-deep: #e8b400;     /* end of the progress gradient */
  --tint-base: #ffffff;     /* base for color-mix tints (badges, options, pills) */
  --glow: rgba(252, 204, 18, 0.35); /* top radial wash on body */
  --masc: #3a5bbf;
  --fem: #bf3a72;
  --scrim: rgba(28, 20, 18, 0.35);  /* dialog backdrop */
  --shadow-dialog: 0 12px 40px rgba(28, 20, 18, 0.18);
  --tint-callout: color-mix(in srgb, var(--senyera-gold) 14%, var(--bg-elevated)); /* rule callout */
  --tint-selected: color-mix(in srgb, var(--senyera-gold) 22%, var(--tint-base));  /* selected option */
  --disabled-fill: var(--accent);        /* disabled primary button */
  --disabled-fill-ink: var(--on-accent);
  --disabled-fill-opacity: 0.45;
}
```

### Dark mode
- `static/app.css` redefines every colour token inside `@media (prefers-color-scheme: dark) { :root { ... } }`, and `:root` sets `color-scheme: light dark` so form controls and scrollbars follow.
- Rules outside `:root` must use tokens, never raw hex, `rgb()` or `white` (`tests/test_dark_mode_css.py` enforces this).
  Add a token with a light and a dark value instead.
- Dark surfaces are warm browns (`--bg #17110e`, `--bg-elevated #221a16`), ink is cream, and the gold stays the same.
  Red buttons keep `#c1001f` with white text, while red *text* (`--senyera-red`, `--link`, `--danger`) is lightened so it stays readable on the dark surface.
- Gold tints use a lower gold share in dark (`--tint-callout`, `--tint-selected`), because gold mixed into a dark brown turns olive.
- A disabled primary button fades to 45% in light, but in dark it becomes a neutral surface with muted text, because faded red on a dark page looks muddy.
- `templates/base.html` sets a `theme-color` meta tag for each scheme so the phone browser bar matches `--bg`; the test checks they stay in sync.
- Check every page in both schemes with `scripts/screenshots.py --dark`.

### Colour roles
- **Red (`--accent` / `--senyera-red`):** brand title, primary buttons, links, current borders.
- **Gold (`--senyera-gold` / `--highlight`):** progress fill, seen dots, rule-callout accent, current-tile inset.
- **Surface:** soft gold wash + optional top radial wash in `body` background - atmosphere without flag chrome.

### Typography
- **Fraunces** (display) for brand, level titles, lesson headings.
- **Figtree** (sans) for UI chrome, buttons, exercises, body.
- Load fonts via Google Fonts **or** system stack fallbacks if offline; do not block app on fonts.

### Motion
- 2–3 intentional motions max (e.g. card flip, progress bar fill, screen fade).
- Prefer `transform` / `opacity`; keep durations ≤ 250ms for UI chrome.

### Screens (IA)
1. `/` - public landing page: positioning `<h1>`, one sentence, "Start learning - it's free" (→ `/signup`) with a quiet "or try a lesson first" link, "How it works" in three numbered steps, a light/dark screenshot of a test question, a closing sign-up button and a footer with "All lessons" and "FAQ" (authed → `/levels`)
   `/lessons` - every A1 lesson grouped by goal, then a sign-up call to action; `/faq` - the FAQ
2. `/signup`, `/signin` - account forms (`gate.js`); `/#signin` forwards to `/signin`
3. `/levels` - "Your A1 course" hub; only open levels (`OPEN_LEVEL_IDS`) show, so A2 and B1 tiles are hidden. Each open level card is a link to the level (counts and bar), then the next goal with its lesson count and a link to all goals, then a primary "Continue: <Lesson>" or "Study vocab: <Deck>" button (`/continue?level=<id>`, from `continue_target`) or "All A1 lessons and vocab done", then a secondary Daily vocab button and the streak. The card link and the buttons are siblings, never nested.
4. `/levels/<id>` - level home (Learn | Vocab tab)
5. `/lessons/<id>` - lesson, public: logged-out visitors get the full Learn and Test tabs, and a perfect Test run ends in a "Create a free account" prompt instead of the done panel
6. `/decks/<slug>` → `/study` | `/browse`

One URL = one job. No multi-screen mega-page. Browser back/refresh keep place.


---

## 6. Content & data

- Runtime source of truth: **SQLite**.
- Authoring/seed: `content/` JSON → `scripts/seed.py` (idempotent).
- Levels: only **A1** is open (`OPEN_LEVEL_IDS`); A2 and B1 rows stay in `content/levels.json` and the database but are hidden.
- Lesson section types stay aligned with prototype: `text`, `rule`, `examples`, `exercise`.
- Vocab retirement: `seen >= 3` per user/card, where `seen` counts Knew it grades.

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
| 2026-11-18 | Screens list updated for the public landing page, /signup and /signin, public lessons and the A1-only hub; plain dashes only |
