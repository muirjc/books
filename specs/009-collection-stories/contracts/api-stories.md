# API contract change: Stories (spec 009)

This change is additive. It is applied to
[spec 001 openapi.yaml](../../001-family-reading-list/contracts/openapi.yaml) and the
generated baseline. Every endpoint needs a signed-in member. Writes need the CSRF header,
as other writes do. 401 and 403 are returned as elsewhere.

## Schemas

- `BookRef`: `{id, title}`.
- `Story`: `{id, title, authors: BookAuthorRef[], series: SeriesRef,
  series_number: string, books: BookRef[], created_by, created_at, updated_by, updated_at}`.
  The number is a string, like `Book.series_number`.
- `StoryAdd`, which takes exactly one of:
  - `{story_id}`, to add an existing story;
  - `{title, author_ids (1–20, unique), series_id, series_number}`, to add a new one.
- `StoryUpdate`: any of `title`, `author_ids`, `series_id`, `series_number`. None may be
  null, and at least one must be present.

## Endpoints

| Method and path | Responses |
|---|---|
| `GET /api/v1/books/{book_id}/stories` | 200 `Story[]`, by series name then number; 404 unknown book |
| `POST /api/v1/books/{book_id}/stories` | 201 `Story` (added); 200 `Story` (the book already had it); 404 unknown book or story; 409 `Conflict` (`story_number_taken`, existing_id, existing_label "#2.5 Title"); 422 |
| `DELETE /api/v1/books/{book_id}/stories/{story_id}` | 204; 404 when the book or story is unknown or the story isn't in the book. The story is deleted when it was in no other book. |
| `GET /api/v1/stories/{story_id}` | 200 `Story`; 404 |
| `GET /api/v1/stories?series_id=` | 200 `Story[]` by number; 404 unknown series |
| `PATCH /api/v1/stories/{story_id}` | 200 `Story`; 404; 409 `Conflict` (`story_number_taken`); 422 |

Book search (`GET /api/v1/books?q=`) may now also return a book because one of its stories'
titles matched. The response shape is unchanged.

*Amended 2026-11-26 by [spec 019](../../019-optional-story-series/contracts/api-stories.md): `series` and `series_number` are nullable together; requests give both or neither.*
