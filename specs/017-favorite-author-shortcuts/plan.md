# Implementation Plan: Favorite Author Shortcuts

**Branch**: `017-favorite-author-shortcuts` | **Date**: 2026-11-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/017-favorite-author-shortcuts/spec.md`

## Summary

- **Star buttons:**
  - The book page byline and my entry page's "All books by …" lines get a star form for
    each author.
  - The form posts to the existing spec 011 `POST /authors/{id}/favorite`, which gains an
    optional, allow-listed `back` return address.
  - The page then shows "Added/Removed <author> …" at `#favorite-notice`.
- **Offer after finishing:**
  - A save that makes a book Finished adds `finished=<book_id>` to its redirect.
  - The landing page works out the offer live from my own entries and favorites (two
    queries) and shows one button per qualifying author.
- **Empty favorites page:** it gets new text and a **Browse the Catalog** link.

Details are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Jinja2 + HTMX (none new)

**Storage**: PostgreSQL 16+; no schema change

**Testing**: pytest (integration), Playwright + axe (a11y), perf suite

**Target Platform**: Single container image (Linux, including the Raspberry Pi 5)

**Project Type**: Web service with server-rendered UI (one deployable)

**Performance Goals**:
- The book page, my entry page and a finishing save stay under 1 s (p95) at 5,000 books.
- The stars add one query per page, and the offer adds two.

**Constraints**:
- No open redirect: `back` is allow-listed, and an entry is accepted only if it's mine
  (R2).
- Works without JavaScript.
- No new session state (Clarifications).

**Scale/Scope**: One family: about 2–10 users and a few thousand books.

## Constitution Check

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | `FavoriteAuthorRepository.among` and `ReadingEntryRepository.finished_counts` are bound to the session user, like every method there. An `/entries/<id>` return address is checked through the bound `ReadingEntryRepository.get`. AC-13 tests give another member favorites and finished books, and check that my stars, counts and offers ignore them. An AC-05 test uses another member's entry as `back`. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Spec, Data Ownership. Favorites and entries are personal and read in place. Nothing records that an offer was shown. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | None. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | AC-01 to AC-15 each get an `ac("017/AC-xx")` test, written failing first. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | No schema change. "A re-read counts once" relies on the existing unique (user, book) entry constraint. Duplicate favorites are prevented by the spec 011 unique constraint. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | `FavoriteForm` gains an optional `back: str` (length-capped). The `finished`, `favorited` and `unfavorited` query values are validated by a new Pydantic model, `FavoriteNoticeQuery` in `schemas/catalog.py` (each an optional UUID; an invalid value becomes none and shows nothing), before any service is called. No JSON API change. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | None stored or sent. |

### Coverage-critical modules (Principle V)

- `src/book_tracker/persistence/favorites.py` (gains `among`) and
  `src/book_tracker/persistence/readings.py` (gains `finished_counts`) are already listed
  and stay at 100%.
- `src/book_tracker/web/favorites.py` is new. It decides which return addresses are
  accepted, including the "my own entry" check. It's added to `scripts/check_coverage.py`
  at 100%.

### New dependencies (Principle VIII)

None.

### Migrations (Principle VI)

- **Schema changes**: None.
- **Destructive changes**: None.

## Project Structure

### Documentation (this feature)

```text
specs/017-favorite-author-shortcuts/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/ui-favorites.md
└── tasks.md
```

### Source Code (repository root)

```text
src/book_tracker/persistence/favorites.py     # among(author_ids)
src/book_tracker/persistence/readings.py      # finished_counts(author_ids)
src/book_tracker/services/authors.py          # favorite_ids, finish_offers
src/book_tracker/schemas/catalog.py           # FavoriteForm.back, FavoriteNoticeQuery
src/book_tracker/web/favorites.py             # new: return addresses, notice, offer (R2, R4)
src/book_tracker/web/quick.py                 # DROPPED_KEYS += finished, favorited, unfavorited
src/book_tracker/web/routes/authors.py        # set_favorite honours back
src/book_tracker/web/routes/readings.py       # finished=<book> on finishing redirects; page contexts
src/book_tracker/web/templates/macros.html               # star_button macro
src/book_tracker/web/templates/partials/favorite_notice.html  # new
src/book_tracker/web/templates/partials/favorite_offer.html   # new
src/book_tracker/web/templates/pages/{book,entry,list,series,add_book,favorite_authors}.html
src/book_tracker/web/static/css/app.css                  # .star-button, author-and-star pairs
scripts/check_coverage.py                                # web/favorites.py
tests/integration/test_favorite_shortcuts.py             # new
tests/a11y/test_favorite_shortcuts_a11y.py               # new
tests/perf/                                              # entry page and finishing save budgets
```

**Structure Decision**: no new route.
- **One module** (`web/favorites.py`) holds the return-address rules and builds the
  notice and the offer, as `web/quick.py` does for spec 015.
- **Two repository methods** supply the personal data.
- **Everything else** is templates and redirect addresses.

## Complexity Tracking

None: every Constitution Check row is Yes.
