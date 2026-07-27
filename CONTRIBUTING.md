# Contributing to La Queta

Thanks for helping. Live app: [la-queta.com](https://la-queta.com). Product intent: `PRODUCT.md`.

## Ways to help

- **Issues** — bugs, content mistakes, UX friction. One issue per problem; Catalan corrections welcome.
- **Pull requests** — small, focused changes. Fork the repo, open a PR against `main`.
- You do **not** need collaborator access; fork → branch → PR is enough.

## Local setup

Stack: Flask + SQLAlchemy + SQLite + vanilla HTML/CSS/JS. Prefer Poetry + the `la-queta` conda env (`environment.yml`).

```bash
conda env create -f environment.yml   # once
conda activate la-queta
poetry install
make upgrade
make seed
make run    # http://127.0.0.1:5001
make test
```

## Before you open a PR

1. Run `make test` and keep it green.
2. Keep diffs small and on-topic — no drive-by refactors.
3. Do **not** edit `prototype/` (frozen reference only).
4. Content scope today is **A1** only; A2/B1 are hub placeholders.
5. Match existing patterns in `STYLE_GUIDE.md` and `TECHNICAL_PLAN.md`.
6. New content: JSON under `content/` (lessons, decks, can-dos); re-seed locally with `make seed`.

## Review

PRs are reviewed manually. Describe *why* the change helps learners or maintainers. Link related issues when you have them.
