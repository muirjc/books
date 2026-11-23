# Contract: Summary drafts in the JSON API (spec 012)

These additions go in `specs/001-family-reading-list/contracts/openapi.yaml`, and the
generated baseline is regenerated. Nothing breaks.

## POST /api/v1/books/{book_id}/summary-drafts

Requests an AI draft for a catalog book. Nothing is stored in the catalog. The request is
CSRF-protected like other API writes.

Request body `SummaryDraftRequest`:

```json
{ "regenerate": false }
```

`regenerate` (boolean, default false) bypasses the cache.

**200** `SummaryDraft`:

```json
{
  "id": "6f0c…",
  "text": "…",
  "source_urls": ["https://openlibrary.org/works/OL…W", "https://en.wikipedia.org/wiki/…"],
  "model": "claude-opus-5-5",
  "series_suggestion": { "name": "The Dresden Files", "number": "2" },
  "cached": false,
  "created_at": "2026-11-23T14:02:11Z",
  "drafts_left_today": 9
}
```

- `series_suggestion` is null when nothing is suggested. Its `number` may be null.

**Errors** use `application/problem+json`, with a `code`:

| Status | code | When |
|---|---|---|
| 404 | not_found | No such book |
| 422 | not_enough_information | The sources say too little |
| 422 | ai_declined | The AI declined, or ended without a draft |
| 422 | draft_rejected | It failed the blocked-site, length or copy check |
| 429 | draft_limit_reached | The member's daily allowance is used up |
| 503 | ai_not_configured | The server has no AI key |
| 503 | ai_unavailable | Timeout (30 s), connection failure or AI service error |

Plus the usual 401 and 403 responses.

## POST /api/v1/books/{book_id}/summaries (changed)

`SummaryCreate` gains an optional `draft_id` (uuid or null).
- With a valid draft for this book (research R6), the summary is stored with origin `ai`
  or `ai_edited`, the draft's model and source URLs.
- With a missing, unknown, expired or other-book id, the origin is `manual`.

The response is unchanged (`Summary` already has `origin`, `model` and `source_urls`).
