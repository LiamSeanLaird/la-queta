# Style Guide — La Queta

Living conventions for humans and AI. Cursor enforces the same via `.cursor/rules/`.
If code and this doc diverge, update both in the same change.

**Product:** La Queta (`la-queta`). **Language taught:** Catalan (vocab field `catalan` stays — that is content, not the brand).

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
- Schema changes **only** via Alembic (`flask db migrate` / `upgrade`). Enable SQLite batch mode.

### Style
- Python 3.12+: use modern typing (`list[str]`, `X | None`).
- SQLAlchemy 2.0 style (`Mapped[]`, `mapped_column`).
- Prefer explicit names over cleverness.
- No comments that narrate what code does; comment only non-obvious intent.
- Keep route handlers thin: validate → call service → return JSON/template.
- Errors: JSON APIs return `{ "error": "..." }` with correct HTTP status; do not leak stack traces to clients.

### Testing
- `pytest` + Flask test client.
- Prefer behaviour tests (HTTP / service) over testing SQLAlchemy internals.
- Use in-memory SQLite in tests (`Testing` config).
- Name tests `test_<behaviour>`.

### Dependencies
- Poetry only. Dev tools in `[tool.poetry.group.dev.dependencies]`.
- Do not `poetry add` a package already constrained in `pyproject.toml` to a different major without updating the existing pin first.

---

## 3. API

- Prefix JSON APIs with `/api/`.
- Auth-required progress endpoints: `401` if no session cookie.
- Resource URLs use stable ids/slugs from the DB (`/api/lessons/<id>`, `/api/decks/<slug>`).
- Request/response bodies: `snake_case` JSON keys.
- No versioning prefix until we have external API consumers.

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
- Avoid generic AI defaults: Inter/Roboto/Arial system stacks as the brand voice; purple-on-white; newspaper broadsheet layouts.

### JS
- Small, explicit functions; no framework patterns.
- Talk to the backend via `fetch` + JSON.
- Progressive enhancement where cheap; study/lesson flows may require JS (acceptable).

---

## 5. Visual design

Intentional **La Queta** look — quiet Catalan learning tool, Senyera-accented — not a marketing landing page.

### Brand signals
- Product name **La Queta** is the primary identity on the home/hub (not the word “Catalan” alone).
- Tagline may reference Catalan / Català (e.g. “aprèn català”).
- Senyera accents allowed: gold `#FCCC12`, red `#C1001F` (thin bar or small accents — not full-page flag wallpaper).

### Tokens (initial)
```css
:root {
  --bg: #f4f0e6;          /* warm paper — content surface */
  --bg-elevated: #fffdf8;
  --ink: #1c1917;
  --muted: #78716c;
  --accent: #0f766e;      /* deep teal — primary actions */
  --senyera-gold: #FCCC12;
  --senyera-red: #C1001F;
  --danger: #b91c1c;
  --radius: 10px;
  --font-ui: "Source Sans 3", "Segoe UI", sans-serif;
  --font-display: "Source Serif 4", "Iowan Old Style", Georgia, serif;
}
```

### Typography
- Display/serif for level titles and lesson headings.
- Sans for UI chrome, buttons, exercises.
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
