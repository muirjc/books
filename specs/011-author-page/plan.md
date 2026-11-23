# Implementation Plan: Author Page and Favorite Authors

**Branch**: `011-author-page` | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)

## Summary

- **Migration 0005** adds `favorite_author`: user, author and `created_at`, with primary key
  `(user_id, author_id)`. The user foreign key is CASCADE and the author foreign key is
  RESTRICT ([data-model.md](data-model.md)).
- **Persistence**: a user-bound `FavoriteAuthorRepository` in
  `persistence/favorites.py`, with `list`, `add`, `remove`, `has` and
  `favorite_authors_condition()`, the My books filter (research R1, R3). The catalog's
  delete-unused rule adds "no favorite" (research R4).
- **Service**:
  - `services/authors.py`: `author_view`, which groups the author's books by series with
    the viewer's entries, adds their stories, and states the viewer's favorite and delete
    status;
  - `add_favorite` and `remove_favorite`;
  - the reason an author can't be deleted.
- **Web**:
  - `/authors/favorites`;
  - `/authors/{id}`;
  - `POST /authors/{id}/favorite`;
  - author links in book rows (an `author_links` macro);
  - the Edit author delete messages;
  - the My books Author filter option `author_id=favorites`.
- **API**:
  - `/api/v1/me/favorite-authors` (GET, PUT and DELETE by author);
  - `favorite_authors` on `/api/v1/me/readings`;
  - 409 `author_is_favorite` on the author delete
    ([contracts/api-favorites.md](contracts/api-favorites.md)).
- **Constitution 2.0.0**: the Principle I exception for the delete refusal, amended in this
  PR.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Jinja2 + HTMX
(no new dependency)

**Storage**: PostgreSQL 16+, with one new table

**Testing**:
- pytest integration tests;
- openapi-core contract tests;
- Playwright with axe (`a11y`);
- `perf`.

**Performance Goals**: SC-001. The Author page makes about six queries:
- the author;
- the books (authors and series loaded by selectin);
- my entries for those books (`list_books`);
- the stories;
- the favorite;
- the delete status.

**Constraints**:
- works without JavaScript;
- WCAG 2.2 AA;
- spec 003 layouts;
- Principle I, with the 2.0.0 exception.

## Constitution Check

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes (with the 2.0.0 exception) | `FavoriteAuthorRepository` is built with the session user and filters every statement by it. No path or body names a member. The Author page reads entries through the user-bound `list_books`. Cross-user tests cover: Ben's page, lists, API and My books filter never reflect Alice's favorites; row equality on the Author page; and the AC-15 refusal shows no name or count. The one disclosure, "some member favorites this author", is the exception added in constitution 2.0.0, which this PR amends and ratifies. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | `favorite_author` is personal, on its own table, holding ids only (spec Data Ownership). |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | None. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | AC-01 to AC-18 each get a `011/AC-xx` test, seen failing first. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | The primary key enforces one favorite per member and author. The author foreign key is RESTRICT, which backstops the delete rule, and the user foreign key is CASCADE. Migration 0005 is tested upgrade → downgrade → upgrade. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | Path ids are UUIDs. The favorite form is validated by `FavoriteForm` (`favorite: Literal["yes", "no"]`), and the My books `author_id=favorites` value is parsed explicitly. The new endpoints and parameter go into `openapi.yaml` and the generated baseline, with contract tests. The UI calls the same services as the API. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | Only member, author and time are stored. Logs hold ids only. |

### Coverage-critical modules

Add `src/book_tracker/persistence/favorites.py` to `scripts/check_coverage.py`. It is a
personal-data repository, like `persistence/readings.py`.

### Migrations

`0005_favorite_authors` creates one table, and its downgrade drops it with its data. Take a
backup first, as usual. The migration runs on app start.

## Project Structure

```text
specs/011-author-page/ spec.md plan.md research.md data-model.md quickstart.md tasks.md
  checklists/requirements.md  contracts/{api-favorites.md, ui-authors.md}
.specify/memory/constitution.md          # 2.0.0
migrations/versions/0005_favorite_authors.py
src/book_tracker/
├── persistence/models.py                # FavoriteAuthor
├── persistence/favorites.py             # FavoriteAuthorRepository (user-bound)
├── persistence/catalog.py               # delete rule + unused list exclude favorites
├── persistence/readings.py              # list(..., favorite_authors=condition)
├── services/authors.py                  # author_view, favorites, delete reason
├── services/catalog.py                  # author_is_favorite conflict
├── services/readings.py                 # list_entries favorite filter
├── schemas/catalog.py                   # FavoriteForm
├── api/favorites.py, api/readings.py    # endpoints
└── web/routes/authors.py, routes/catalog.py, routes/readings.py,
    templates/pages/{author,favorite_authors}.html, macros (author_links), edit_author,
    entry, edit_book, list, CSS
tests/integration/test_author_page.py, test_favorite_authors.py
tests/contract/test_favorites_contract.py
tests/a11y/test_author_a11y.py
tests/perf (author page, favorites)
```

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| Principle I exception (constitution 2.0.0) | The maintainer chose to keep favorited authors from deletion | Cascade-delete the favorites. It was rejected by the maintainer in clarification. |
