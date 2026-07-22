# Catalan Learning App — Product Document

## Goal
A personal, local tool to help Liam learn Catalan. No hosting, no user management. Built to evolve as usage reveals what's actually useful.

## Principles
- **Start simple, add on use.** Features are added when needed in real learning sessions, not speculatively.
- **Portable data.** All progress stored in plain JSON — inspectable, editable, portable.

---

## Features

### v1 — Core Flashcards ✅ complete 2026-06-04
- [x] Flashcard quiz: English → Catalan and Catalan → English
- [x] Starter deck: greetings, numbers, common phrases
- [x] Progress persisted in local JSON file
- ~~Spaced repetition (SM-2)~~ — removed, see v2

### v2 — Web UI + Multiple Decks ✅ complete 2026-06-04
- [x] Replace SM-2: show each card 3 times, then retire it
- [x] Web UI: Flask backend + HTML/JS frontend
- [x] Card flip interaction, Enter key to advance
- [x] Progress bar per session
- [x] Home screen with deck list (Starter, Everyday, Travel)
- [x] Deck detail: Study mode and Browse mode
- [x] Browse: full scrollable vocab list with seen-dots

### v3 — Learn Section (current)
- [ ] Learn tab on home screen
- [ ] Lesson list with completion state
- [ ] Lesson page: text, rule, example, and exercise sections
- [ ] Multiple-choice exercises with answer + explanation
- [ ] Lesson progress persisted in `progress.json`
- [ ] Initial lessons: noun gender, definite articles, ser vs estar, present tense verbs

### Backlog (not yet prioritised)
- Add new cards via UI
- Tag/topic filtering
- Pronunciation hints
- Example sentences on cards
- Import from CSV
- Daily streak tracking

---

## Out of Scope (for now)
- User accounts / authentication
- Remote hosting
- Audio playback
- Mobile app
