# Implementation Plan: Delete an Author With No Books

**Branch**: `008-delete-unused-authors` | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)

## Summary

- **Persistence** (`persistence/catalog.py`):
  - `author_books(author_id)` returns the books linked to the author, by title;
  - `unused_authors()` returns authors with no `book_author` row, by sort name;
  - `unused_author_count()`;
  - `delete_unused_author(author_id)` is one statement:
    `DELETE FROM author WHERE id = :id AND NOT EXISTS (SELECT 1 FROM book_author WHERE
    author_id = :id) RETURNING id`. It is atomic, so an author that gained a book is not
    deleted. The `book_author_author_id_fkey ON DELETE RESTRICT` is the backstop, and its
    `IntegrityError` is mapped to the same conflict.
- **Service** (`services/catalog.py`), `delete_author(db, actor_id, author_id)`:
  - unknown author: `NotFoundError`;
  - the author has books: `ConflictError("author_has_books", ...)`;
  - deleted: an info log line with the actor and author ids.
- **API:** `DELETE /api/v1/authors/{author_id}` returns `204`, `404` or `409`.
- **UI:**
  - `GET /catalog/authors/unused` (new);
  - `POST /catalog/authors/{id}/delete`, which without `confirm=yes` shows the confirm page
    (the confirm_remove pattern);
  - Edit author lists the author's books and offers Delete author only when there are
    none;
  - My books links to the list when the count is above 0.

No schema change and no new dependency.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Jinja2 + HTMX

**Storage**: PostgreSQL 16+ (no change)

**Testing**: pytest + testcontainers; openapi-core contract tests; Playwright + axe (`a11y`);
`perf`

**Performance Goals**: SC-003. Both the anti-join and the count use the existing
`book_author` primary key and its `author_id` index.

**Constraints**: works without JavaScript (POST forms with CSRF); WCAG 2.2 AA; spec 003
layouts.

## Constitution Check

| # | Gate | Yes / No | How |
|---|---|---|---|
| I | Personal data is filtered by session user in the data-access layer, with cross-user tests | Yes | No personal data is read or written. The pages need a signed-in member, and tests check that a signed-out request is refused. |
| II | Catalog vs personal data placement is stated; no duplication | Yes | Catalog only (spec Data Ownership). Reading entries can't reference an author. |
| III | Any AI output is draft-only until accepted, with provenance stored and a manual fallback | Yes | No AI. |
| IV | All external sources are permitted APIs behind adapters; excluded domains are blocked | Yes | None. |
| V | Tests are written first; every AC maps to a feature-qualified test | Yes | AC-01 to AC-09 each get an `008/AC-xx` test, seen failing first. |
| VI | Rules are enforced by DB constraints; migrations are reversible | Yes | "No books" is enforced by the conditional delete and by the existing RESTRICT foreign key. There is no migration. |
| VII | Pydantic v2 models validate all input; every JSON API endpoint has an OpenAPI contract | Yes | The author id is a typed path UUID, and `confirm` is a literal check. The new endpoint is added to `openapi.yaml` and the generated baseline; the change is in `contracts/api-delete-author.md`, with a contract test. |
| VIII | No new deployables or datastores; new dependencies are justified | Yes | None. |
| IX | No new personal data beyond the minimum; nothing personal sent to external services; secrets handled correctly | Yes | The log line holds ids only. |

### Coverage-critical modules

Unchanged. `persistence/catalog.py` is not on the list; the new code is fully covered by
integration tests anyway.

### Migrations

None.

## Project Structure

```text
specs/008-delete-unused-authors/
├── spec.md  plan.md  tasks.md  quickstart.md
├── checklists/requirements.md
└── contracts/{ui-delete-author.md, api-delete-author.md}

src/book_tracker/
├── persistence/catalog.py        # author_books, unused_authors(+count), delete_unused_author
├── services/catalog.py           # delete_author, author_books, unused_authors
├── api/authors.py                # DELETE /authors/{id}
└── web/
    ├── routes/catalog.py         # /catalog/authors/unused, /catalog/authors/{id}/delete
    ├── routes/readings.py        # unused-author count on My books
    └── templates/pages/{edit_author,unused_authors,confirm_delete_author,list}.html

tests/
├── integration/test_delete_author.py
├── contract/test_delete_author_contract.py
└── a11y/test_delete_author_a11y.py
```

## Complexity Tracking

Nothing to justify.
