# API contract changes: Upcoming books (spec 007)

All changes are additive. They are applied to
[spec 001 openapi.yaml](../../001-family-reading-list/contracts/openapi.yaml) and the
generated baseline `openapi.generated.json`.

| Component / path | Change |
|---|---|
| `Book` (response) | + `release_date`: `string` (`date`) or `null`, required in responses |
| `BookCreate` (and `ReadingEntryCreate.new_book`) | + optional `release_date`: `date` or `null` |
| `BookUpdate` | + optional, nullable `release_date` (null clears) |
| `ReadingEntry` (response) | + `pre_ordered`: `boolean`, required in responses |
| `ReadingEntryCreate` | + optional `pre_ordered`: `boolean`, default `false` |
| `ReadingEntryUpdate` | + optional `pre_ordered`: `boolean` (not nullable) |
| `GET /api/v1/me/readings` | + query `upcoming`: `boolean`, default `false`. When true: only entries with `release_date` after today, soonest first, and `sort` ignored |

Breaking changes: none. Contract tests (`tests/contract/test_upcoming_contract.py`) check
the new fields and the filter against the committed `openapi.yaml`.
