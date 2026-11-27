# API contract: rating on my entries (spec 020)

The published contract is `specs/001-family-reading-list/contracts/openapi.yaml`; this note
lists the changes. None is breaking: every new field and parameter is optional.

## Schemas

- `ReadingEntryCreate.rating`: integer 1–5 or null, optional (default null).
- `ReadingEntryUpdate.rating`: integer 1–5 or null, optional. Left out: unchanged. Null:
  cleared.
- `ReadingEntry.rating` (response): integer 1–5 or null, always present.

A value outside 1–5 (or not an integer) → 422 problem response.

## `GET /api/v1/me/readings`

- `sort` gains `rating` (lowest first) and `-rating` (highest first). Unrated entries come
  last in both, then by title.
- New optional `min_rating` (integer 1–5): only entries rated at least that.
- New optional `rated` (boolean): `true` only rated entries, `false` only unrated ones.
- Both combine with `q`, `author_id`, `series_id`, `status`, `favorite_authors` and paging.

## Privacy

- Only the caller's own entries carry a rating. `GET/PATCH/DELETE /me/readings/{id}` for
  another member's entry → 404, as today.
- No catalog schema (`Book`, `Series`, `Author`, stories, catalog lists) gains a rating.
