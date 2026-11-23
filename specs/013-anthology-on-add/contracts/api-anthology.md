# API contract change: stories when creating an entry with a new book (spec 013)

`POST /api/v1/me/readings` (the existing "Add a book to my list" operation) accepts an
optional `stories` list. It is a non-breaking addition: omitting it behaves as before
(AC-27).

## Request

```json
{
  "new_book": {
    "title": "Side Jobs",
    "author_ids": ["<jim-butcher>"],
    "series_id": "<dresden-files>"
  },
  "status": "finished",
  "stories": [
    {"title": "Restoration of Faith", "series_number": "1.5"},
    {"title": "Publicity and Advertising", "series_number": "2.5"},
    {"story_id": "<existing-story>"}
  ]
}
```

`NewBookStory`: either `story_id` alone, or a new story.

| Field | Required | Default |
|---|---|---|
| `story_id` | for an existing story | — |
| `title` | for a new story | — |
| `series_number` | for a new story | — |
| `series_id` | no | `new_book.series_id`; required if that is null |
| `author_ids` | no | `new_book.author_ids` |

The `stories` list holds at most 50 items. No two items may share an effective
(series, number) pair or a `story_id`.

## Responses

| Status | When | Body |
|---|---|---|
| 201 | Saved: the book, the entry and every story | `ReadingEntry` (unchanged) |
| 422 | Any rule above, or `stories` with `book_id` (AC-23, AC-24, AC-26) | `HTTPValidationError` / `Problem` naming `stories.{i}...` |
| 409 | An item's series and number belong to an existing story (AC-25) | `Problem`, `code: story_number_taken`, `existing_id` = the story |
| 404, 401, 403 | As today | `Problem` |

On any error, nothing is saved.

The stories can be read back with the existing `GET /api/v1/books/{id}/stories` (spec 009).
