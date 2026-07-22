# Catalan Learning App — Technical Plan

## Stack
- **Language:** Python 3
- **Interface:** Web UI — Flask backend, vanilla HTML/JS/CSS frontend
- **Storage:** Local JSON files (`data/progress.json`)
- **Entry point:** `app.py`
- **Dependencies:** `flask` (managed via Poetry)

---

## File Structure
```
catalan/
├── app.py                      # Flask app + API routes
├── store.py                    # Load/save JSON progress
├── templates/
│   └── index.html              # Single-page UI (all screens)
├── data/
│   ├── starter_deck.json       # Vocab deck: greetings, numbers, basics (37 cards)
│   ├── everyday_deck.json      # Vocab deck: time, days, food, adjectives (40 cards)
│   ├── travel_deck.json        # Vocab deck: transport, places, directions (40 cards)
│   └── progress.json           # User progress — auto-created
├── lessons/
│   ├── 01-noun-gender.json
│   ├── 02-definite-articles.json
│   ├── 03-ser-vs-estar.json
│   └── 04-present-tense.json
├── pyproject.toml
├── PRODUCT_INXS.md
└── TECHNICAL_PLAN_INXS.md
```

---

## Data Models

### Vocab card (`*_deck.json`)
```json
{
  "id": "greet_001",
  "catalan": "Bon dia",
  "english": "Good morning",
  "hint": "",
  "tags": ["greetings"],
  "grammar": "noun-gender"
}
```
`grammar` is optional — links a card to the lesson that explains its rule.

### Vocab progress (`progress.json`)
```json
{
  "cards": { "greet_001": { "seen": 3 } },
  "lessons": { "noun-gender": { "completed": true, "exercises_correct": 3 } }
}
```

### Lesson file (`lessons/*.json`)
```json
{
  "id": "noun-gender",
  "title": "Noun Gender",
  "order": 1,
  "summary": "Every noun in Catalan is masculine or feminine.",
  "sections": [
    { "type": "text",     "content": "Unlike English, every Catalan noun has a gender..." },
    { "type": "rule",     "content": "Most nouns ending in -a are feminine." },
    { "type": "examples", "items": [
      { "catalan": "el gat",   "english": "the cat (m)" },
      { "catalan": "la porta", "english": "the door (f)" }
    ]},
    { "type": "exercise", "kind": "multiple_choice",
      "question": "What gender is 'taula' (table)?",
      "options": ["Masculine", "Feminine"],
      "answer": "Feminine",
      "explanation": "It ends in -a, so it's feminine: la taula."
    }
  ]
}
```

#### Section types
| Type | Purpose |
|---|---|
| `text` | Prose explanation |
| `rule` | Highlighted rule callout |
| `examples` | Table of catalan/english pairs with optional notes |
| `exercise` | Interactive question (currently: `multiple_choice`) |

---

## Repetition Logic (vocab)
- Each card has a `seen` count (default 0)
- Included in session until `seen >= 3`, then permanently retired
- No rating — user just flips and moves on

## Lesson Completion Logic
- Lesson marked complete when all exercises answered (regardless of correctness)
- Correct/total stored for reference; no re-testing forced

---

## Running the App
```bash
poetry install
poetry run python app.py
# Open http://localhost:5001
```

## API Routes
| Method | Route | Description |
|---|---|---|
| GET | `/` | Serve the UI |
| GET | `/api/decks` | List all decks with progress stats |
| GET | `/api/decks/<slug>/cards` | All cards in a deck |
| GET | `/api/decks/<slug>/session` | Shuffled unretired cards |
| POST | `/api/seen/<id>` | Increment seen count |
| GET | `/api/lessons` | List all lessons with completion state |
| GET | `/api/lessons/<id>` | Full lesson content |
| POST | `/api/lessons/<id>/complete` | Mark lesson complete, save exercise score |

---

## Implementation Phases

### Phase 1 — MVP ✅ complete 2026-06-04
- [x] CLI flashcard app with SM-2 spaced repetition
- [x] Starter deck: 37 cards

### Phase 2 — Web UI + Multiple Decks ✅ complete 2026-06-04
- [x] Flask app, single-page UI
- [x] Home → Deck → Study / Browse flow
- [x] Everyday deck (40 cards), Travel deck (40 cards)
- [x] Enter key binding, seen-dots in browse view

### Phase 3 — Learn Section (next)
- [ ] Migrate progress.json to `{ cards: {}, lessons: {} }` shape
- [ ] `store.py`: lesson load/save helpers
- [ ] `app.py`: lesson API routes
- [ ] `index.html`: Learn tab, lesson list, lesson page renderer
- [ ] 4 initial lesson files

### Phase 4 — Content & Enrichment
- [ ] Add cards via UI
- [ ] Pronunciation hints
- [ ] Tag/topic filtering
- [ ] More lessons (negation, object pronouns, past tense)

---

## Decisions Log
| Date | Decision | Reason |
|---|---|---|
| 2026-06-04 | Python stdlib only initially | Zero setup |
| 2026-06-04 | Switched to Flask + web UI | Terminal too lean for daily use |
| 2026-06-04 | SM-2 dropped for simple seen-count | User prefers fixed 3-view rule, no ratings |
| 2026-06-04 | Poetry for dependency management | User preference |
| 2026-06-04 | Lessons separate from vocab decks | Grammar needs explanation + exercises, not just flashcards |
| 2026-06-04 | Lessons as JSON with typed sections | Easy to author new content without touching code |
