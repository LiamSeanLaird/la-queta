# Contributing to La Queta

Thanks for helping. Live app: [la-queta.com](https://la-queta.com). Product intent: `PRODUCT.md`.

## Ways to help

- **Issues** - bugs, content mistakes, UX friction. One issue per problem; Catalan corrections welcome.
- **Pull requests** - small, focused changes. Fork the repo, open a PR against `main`.
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
2. Keep diffs small and on-topic - no drive-by refactors.
3. Do **not** edit `prototype/` (frozen reference only).
4. Content scope today is **A1** only; A2/B1 are hub placeholders.
5. Match existing patterns in `STYLE_GUIDE.md` and `TECHNICAL_PLAN.md`.
6. New content: JSON under `content/` (lessons, decks, can-dos); re-seed locally with `make seed`.
7. Noun cards carry their article (`la mare`, `l'avi`), a `gender` of `m` or `f`, and a `plural` with its article (`les mares`, `els avis`), or the no-plural marker.
   Day, month and sign cards may show the bare word. `tests/test_card_format.py` enforces this.
   A card that starts with a lowercase article (`la data de naixement`) is a noun, even when it is several words long.
   Every card's `pos` is one of `noun`, `verb`, `adjective`, `adverb`, `pronoun`, `number`, `interjection` or `phrase`.
8. Every lesson has a `words` list of `{"catalan", "english"}` entries: every Catalan word its test asks the learner to produce or recognise, with nouns carrying their article (`la taula`, not `taula`).
   Each listed word must also appear on the Learn tab, in the text or an example.
   `tests/test_lesson_content.py` enforces both; if it flags a word, teach it in the lesson or change the test item, rather than adding to its allow-lists.
9. Never change a lesson `id` or a card `id`, and never delete a card: learners' progress is keyed by them, and lesson ids are public URLs.

## Review

PRs are reviewed manually. Describe *why* the change helps learners or maintainers. Link related issues when you have them.
