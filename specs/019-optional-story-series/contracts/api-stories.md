# API contract: Stories without a series (spec 019)

Changes to the spec 009 ([api-stories](../../009-collection-stories/contracts/api-stories.md))
and spec 013 ([api-anthology](../../013-anthology-on-add/contracts/api-anthology.md))
contracts. Routes are unchanged.

## `Story` (response)

```json
{"id": "…", "title": "The Lottery", "authors": [ … ],
 "series": null, "series_number": null, "books": [ … ]}
```

`series` (`SeriesRef | null`) and `series_number` (`string | null`) are null together for a
story without a series.

## Requests

| Schema | Rule |
|---|---|
| `StoryAdd` (new story) | `title` and `author_ids` required. `series_id` and `series_number` both given or both left out; one alone → 422. |
| `StoryUpdate` | `series_id` and `series_number` may be set to `null`, together; one alone (set or null) → 422. |
| `NewBookStory` (`stories` on entry create) | `title` required. No number and no `series_id` → no series. A number without `series_id` takes the new book's series; 422 when the book has none. `series_id` without a number → 422. |

- Duplicate checks (`story_number_taken` 409, "same series and number" 422) apply only to
  stories with a series.
- `GET /api/v1/books/{book_id}/stories` lists stories with a series by series name then
  number, then stories without a series in the order they were added to the book.
- `GET /api/v1/stories?series_id=` never returns a story without a series.
