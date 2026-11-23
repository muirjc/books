# Data Model: AI Summary Drafts (spec 012)

Migration `0006_summary_drafts`. It is reversible: `downgrade` drops both tables.

## summary_draft (catalog cache, research R6)

| Column | Type | Rules |
|---|---|---|
| id | uuid | PK `summary_draft_pkey` |
| draft_key | text | not null; `ta:<title>\|<authors>`, prefixed by `isbn:<13 digits>\|` when there is an ISBN |
| text | text | not null; CHECK `length(btrim(text)) > 0` (`summary_draft_text_check`) |
| source_urls | jsonb | not null; a JSON array of up to 20 URL strings |
| model | varchar(100) | not null; the model that answered |
| series_name | varchar(200) | null |
| series_number | numeric(5,2) | null; CHECK 0–999.99 (`summary_draft_series_number_check`) |
| created_at | timestamptz | not null, default `now()` |

- Index `summary_draft_key_created_idx` on `(draft_key, created_at DESC)`.
- There is no foreign key to `book`: a draft made on Add a book exists before its book. A
  draft matches a book through `draft_key`.
- Rows older than 30 days are deleted when a new draft is written. A lookup ignores them
  anyway.
- No user column: a draft is catalog data, shared by the family. The member who asked is
  recorded only on the summary they save.

## ai_draft_usage (personal, research R8)

| Column | Type | Rules |
|---|---|---|
| user_id | uuid | FK → app_user `ai_draft_usage_user_id_fkey` ON DELETE CASCADE |
| day | date | not null |
| count | integer | not null; CHECK `count >= 1` (`ai_draft_usage_count_check`) |

- PK `ai_draft_usage_pkey (user_id, day)`.
- Read and written only by `DraftUsageRepository(db, user_id)`.
- Rows older than 30 days are deleted on reserve.

## source_lookup_cache (existing, spec 002)

The CHECK `source_lookup_cache_kind_check` is replaced to allow `'book_description'` as
well. The downgrade first deletes those rows, then restores the old check. Key:
`sha256(draft_key)` in hex (research R3).

## book_summary (existing)

No schema change. `persistence.catalog.save_summary` gains `model` and `source_urls`
parameters. The existing CHECK `book_summary_ai_model_check` (`origin = 'manual' OR model
IS NOT NULL`) already enforces that AI summaries name their model.

## Domain values (no table)

- `BookFacts(title, authors: tuple[str, ...], series_name, series_number, isbn13,
  release_year)`: the only input to the AI request (R7).
- `BookDescription(work_url, description)`, from Open Library.
- `GeneratedDraft(status, text, source_urls, cited_urls, series_name, series_number,
  model)`, from the generator.
- `DraftView(id, text, source_urls, model, series_name, series_number, cached,
  created_at, drafts_left)`: what pages and the API show.

## Origin rule (R6)

`origin_for(draft, book_key, saved_text, today)`:
- `manual` when the draft is missing, older than 30 days, or for another key;
- otherwise `ai` when the normalized text equals the draft's;
- else `ai_edited`.

The model and source URLs are copied from the draft only for `ai` and `ai_edited`.
