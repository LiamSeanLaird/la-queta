# La Queta - Product Document

## Goal
**La Queta** is free Catalan for complete beginners.
It is a short, complete web course that takes someone from zero to A1: 20 grammar and topic lessons, each with a short test, plus vocab flashcard decks.
Anyone can read every lesson and take its test without an account.
A free account saves progress, so learners can pick up on any device.

The positioning line is "Free Catalan for complete beginners", with "aprèn català" as the small Catalan accent line under the brand.

## Principles
- **Free to use, free to run.**
  No paid SaaS; host on an Oracle Always Free VM.
- **One course, A1 only.**
  The site is pitched as the A1 starting point, not as one level among several.
  The code stays general by level, so A2 can ship later without a rewrite.
- **Try before signing up.**
  Lessons are public; an account is only needed to save progress and to study vocab.
- **Honest copy.**
  No invented numbers (hours, learner counts) and no hype.
  Only state what is true of the app.
- **Findable.**
  Public pages are server-rendered and crawlable, so the lessons can rank for the beginner searches they answer (for example "Catalan ser vs estar", "Catalan numbers").
- **Prototype is reference only.**
  UX and content patterns live in `prototype/`; do not extend that app.

---

## Scope

### In scope
- Public web app (no install).
- Public landing page on `/`, a public lesson list on `/lessons`, a public FAQ on `/faq`, and public lesson pages (Learn and Test) for logged-out visitors.
- Email + password accounts with a cookie session (simple auth, not security-hardened).
- One course: A1.
  A2 and B1 rows exist in the database but are hidden from the hub until content ships; the hub reads "Your A1 course".
- Lessons with text, rules, examples and a Test (multiple choice, cloze, type-in, listening, speak self-check).
- Vocab decks with self-graded flashcards on a spaced repetition schedule, plus browse and a daily vocab session with a streak.
- A "You've finished A1" moment when every A1 lesson is done.
- On-page SEO and crawl basics: unique titles and descriptions, canonical URLs, JSON-LD, `robots.txt`, `sitemap.xml`, and a `www` to apex redirect.
- SQLite persistence for users, content and progress.
- Deploy on an Oracle Always Free VM.

### Out of scope (for now)
- A2 / B1 / B2 **content** (not shown on the hub until it ships).
- Public vocab: deck pages, study, browse, daily vocab and `/levels` need an account.
- OAuth, email magic links, password-reset email.
- Hosted audio files, cloud speech recognition, LLM speaking (browser text-to-speech and the speak self-check are in).
- Mobile native apps.
- Third-party analytics, trackers or cookie banners.
- Paid hosting or multi-instance scaling.
- Adding cards or lessons via an admin UI (seed and migrate instead).

---

## User identity
- **Name** (stored as `handle`), **email** and **password** are required to create an account.
- Email shape is checked with a regex only; there is **no verification mail**.
- Passwords are hashed (Werkzeug) and never stored or returned in plaintext.
- Sign in with email + password on any device; the session cookie lasts about a year.
- Learners can change their name and email from the profile dialog.
- No OAuth or magic links yet.
- Purpose: cross-device progress with a simple account.

---

## Learning flow

### Logged-out visitor
```
Home (/): short pitch, "Start learning - it's free" (→ /signup) or "or try a lesson first" (→ lesson 1),
  "How it works" in three steps, footer links to /lessons and /faq
  → Lesson (Learn | Test), with previous / next lesson links and "All lessons"
    → Test all correct → "Create a free account to save this lesson and keep going"
      → /signup or /signin → the lesson is saved as complete → back on the lesson, "Saved to your account."
```

- The lesson completion is carried over by re-posting it after sign-up or sign-in through the same validated completion API the logged-in path uses; the server never trusts the client's word that a lesson is done.
- `/signup` and `/signin` hold the account forms; old `/#signin` links still work.
- After sign-up with no lesson to save, the new learner goes to `/continue`, which opens lesson 1; after sign-in they go to the `/levels` hub.
- `/signup` says in one line what the account gives: progress saved on any device, vocab flashcards and a daily review.

### Logged-in learner
```
/ → /levels (hub: "Your A1 course", lessons done, words learned, progress bar, daily vocab)
  → /levels/a1 (lessons grouped by goal, vocab decks)
       → Lessons (ordered list, completion state)
       → Vocab decks: study, browse
  → /levels/a1/daily (daily vocab session)
```

- Default path: `/continue` goes to the next incomplete lesson, or to a deck with cards left once every lesson is done.
- A lesson is complete when its Test finishes with every question correct.
- Finishing a lesson that completes a goal shows a "Goal complete" dialog.
- Finishing the last A1 lesson shows "You've finished A1" on the lesson and on the hub: keep reviewing vocab daily, and A2 is not here yet.

### Vocab
- Study shows a card, the learner flips it, then grades it **Knew it** or **Not yet**.
- **Knew it** moves the card up a review ladder (1, 3, 7, 14, 30, 60 days) and counts as one more view; **Not yet** makes the card due again now.
- A card is **retired** (counted as a learned word) after the learner knew it 3 times.
- Study sessions put due reviews first, then new cards in deck order, then reviews not due yet.
- Daily vocab puts due reviews first, then new words from decks the learner has started or whose lesson they completed, then the next decks in order, then retired cards.
  Finishing it each day builds a streak.
- Learners can **Retire now** from study or browse.
  When a deck is fully retired, **Unretire deck** makes every card new again.

---

## Level completeness
Shown on the hub as a single % per level, derived from:
- lesson completion ratio (primary);
- vocab retirement ratio (secondary; weight defined in the technical plan).

Do not invent a third progress system.

---

## Features

### Phase A - Foundation
- [x] App skeleton at repo root (Flask + Poetry + pytest)
- [x] SQLite + Alembic models and migrations
- [x] Simple email + password auth (no OAuth, no email verification)
- [x] Level hub with empty or seeded progress

### Phase B - Content & Learn
- [x] Seed A1 lessons from `prototype/` (all → A1; A2 scaffold empty)
- [x] Lesson list + lesson page (sections + exercises)
- [x] Lesson progress persisted per user

### Phase C - Vocab
- [x] Decks scoped to a level
- [x] Study + browse modes (patterns from the prototype UI)
- [x] Per-user card progress

### Phase D - Polish & ship
- [x] Multi-page UX (home → levels → level → lesson / deck)
- [x] Continue UX
- [x] Deploy to Oracle Always Free VM, live at https://la-queta.com; see `DEPLOY.md`
- [x] Backup story for the SQLite file (on-VM cron; optional Mac pull)

### Phase E - Vocab UX
- [x] Study: **Enter**, **Space**, Show answer or a card tap flips to English, then **Knew it** (key 2) or **Not yet** (key 1) grades the card; each card is graded at most once per session, even after **Back**, and Not yet cards come back once at the end
- [x] Spaced repetition: graded cards are scheduled on the 1, 3, 7, 14, 30, 60 day ladder
- [x] Browse: retired badge and muted row for retired cards
- [x] **Retire now** on study + browse
- [x] **Unretire deck** when all cards are retired
- [x] **Daily vocab** with a streak
- [ ] Later (optional): browse filter active vs retired

### Phase F - A1 Practice
- [x] Learn | Practice tabs; multiple choice, cloze and type-in; complete only after a perfect Practice.

### Phase G - A1 path
- [x] Programme theme coverage filled (**20** A1 lessons; see `content/a1_coverage.md`)
- [x] **7 clustered goals** (`content/a1_can_dos.json`) and a "Goal complete" dialog
- [x] Browser text-to-speech listening + speak self-check in Practice

### Phase H - Public A1 course and SEO
- [x] Public lesson pages (Learn and Practice) for logged-out visitors, with previous / next links
- [x] Sign up after Practice saves the lesson as complete
- [x] Public landing page on `/`; account forms on `/signup` and `/signin`
- [x] Short landing page that leads to sign-up; lesson list on `/lessons`, FAQ on `/faq`
- [x] A1-only hub ("Your A1 course") and "You've finished A1" moment
- [x] Unique titles and descriptions, canonical URLs, noindex on account-only pages, one `<h1>` per page, `lang="ca"` on Catalan text
- [x] JSON-LD: `Course` on `/`, `FAQPage` on `/faq`, `LearningResource` on lessons
- [x] `robots.txt`, `sitemap.xml`, `www` to apex redirect
- [ ] Register the site in Google Search Console and submit the sitemap (human step; see `DEPLOY.md`)

### Next (content / product)
- A2 content, once A1 is solid
- Denser practice banks; richer exam-shaped reading and writing
- Hosted audio / LLM speaking (optional)
- Difficulty ratings beyond Knew it / Not yet (optional)
- OAuth; email verification / magic link / password reset email (optional)

---

## Content sources
Reuse and re-level material from `prototype/data/` and `prototype/lessons/`.
New lessons and decks are authored as seed data, not by changing the prototype app.

**Level assignment (locked):** all current prototype decks and lessons seed into **A1**.
**A2** and **B1** exist in the database but are hidden from the hub until content is authored.

**Stable ids (locked):** never change a lesson `id` or a card `id`, and never delete a card.
Learner progress is keyed by these ids, and lesson ids are public URLs.

## Success criteria
- A stranger can find a lesson on Google, read it and finish its Test without an account.
- They can create an account from that lesson, have it saved as complete, study vocab, sign in later on another device and see their progress.
- A learner can work through all 20 lessons and reach the "You've finished A1" moment.
- Operator cost: **$0**/month within Oracle Always Free limits.
