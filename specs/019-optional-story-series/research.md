# Research: Stories Without a Series (spec 019)

## R1 – The schema

- **Decision**: migration `0007_optional_story_series`:
  - `story.series_id` and `story.series_number` become nullable.
  - A new CHECK, `story_series_both_or_neither`:
    `(series_id IS NULL) = (series_number IS NULL)` (AC-03, AC-04 at the database).
  - The unique index `story_series_number_uq (series_id, series_number)` is unchanged.
    PostgreSQL treats NULLs as distinct, so any number of stories may have no series,
    while stories with a series stay one per series and number (FR-002).
  - The range CHECK `story_series_number_range` passes for NULL as it is.
  - `book_story.position` (integer, NOT NULL): the order a story was added to that book
    (AC-09). Existing rows are numbered per book by series name, then number, which is
    today's order, so nothing visible moves.
- **Downgrade**: refuses, with a clear message, while any story has no series (spec edge
  case "Undoing the change"). Otherwise it drops the CHECK and `position`, and makes the two
  columns NOT NULL again (AC-14).
- **Alternatives considered**:
  - A placeholder "No series" series: rejected, because it would show on the Series view,
    in the series type-ahead and in counts, and is the made-up data the bead complains of.
  - Ordering by `created_at` of the link: `book_story` has no timestamp, and timestamps
    within one save are equal. A position is explicit.

## R2 – Adding to a book in order

- **Decision**: `book_story.position` defaults to `nextval('book_story_position_seq')`.
  Every new link takes the next value, so within a book a later story always sorts after an
  earlier one, and spec 013's one-save anthology links the rows in their form order. The
  sequence starts after the backfilled positions.
- **Rationale**: no extra query on insert, and two concurrent adds never share a position.
  Positions are only compared within a book, so gaps between books don't matter.
- **Alternatives considered**: `coalesce(max(position), 0) + 1` per book in an
  `INSERT … SELECT`: rejected during implementation, because concurrent adds could share
  a position, and every insert of a link (including test set-up and spec 013's batch)
  would need the extra subquery.

## R3 – Listing a book's stories

- **Decision**: `persistence.catalog.book_stories` outer-joins `series` and orders by
  `series_id IS NULL`, `lower(series.name)`, `series_number`, `book_story.position`,
  `story.id` (AC-09).
- `story_matches` (spec 009 R7, the type-ahead's "contains …") orders by
  `series_number NULLS LAST`, then position.
- `series_stories` already filters on the series, so stories without one never reach a
  series page, its progress counts or its Add #next row (AC-11).

## R4 – The domain and the labels

- **Decision**: `domain.Story.series` becomes `SeriesRef | None` and `series_number`
  `Decimal | None`; mypy --strict then finds every place that assumed a series.
- `services.catalog.story_label` gives "#2.5 Publicity and Advertising" with a series and
  just the title without one.
- **Templates** (AC-08): `partials/book_stories.html` (book page, entry page, Edit book),
  `pages/author.html` (Stories list) and `pages/edit_story.html` ("All of <series>") show
  the series parts only when there is a series. Edit author already lists titles only.

## R5 – The forms

- **Add a book's story rows** (`web/forms.py`, `web/anthology.py`; spec 013):
  - no number and no series → a story without a series (AC-01), whatever the book's series;
  - a number and a blank series → the book's series (AC-02); with no book series, the
    reworded spec 013 AC-11 message (AC-07);
  - a series and no number → "Story N: Enter a number, or clear the series for a story that
    isn't part of a series" (AC-03);
  - duplicate checks (spec 013 AC-12, AC-13) and the existing-story offer apply only to
    rows with a series.
  - The hint changes to say a blank number and series make a story without a series.
- **Add a story** (`web/routes/stories.py`, spec 009 AC-02): the series still starts with
  the book's. Clearing it and leaving the number blank adds a story without a series
  (AC-04); a series with no number, or a number with no series, is refused beside the field.
- **Edit story** (AC-05): clearing both makes it a story without a series; giving both
  follows spec 009 AC-16.
- **Title suggestions** (AC-06): unchanged, so an existing story without a series can be
  added to another book by choosing it.

## R6 – The JSON API

- **Input** (Pydantic, Principle VII):
  - `StoryAdd`: a new story needs `title` and `author_ids`; `series_id` and `series_number`
    are both given or both left out.
  - `StoryUpdate`: `series_id` and `series_number` may be set to null, together.
  - `NewBookStory` (spec 013) and `ReadingEntryCreate.stories`: no `series_number` and no
    `series_id` → no series; a number with no `series_id` takes the new book's series, and
    is refused when the book has none; a `series_id` with no number is refused. Duplicate
    checks apply only to items with a series.
- **Output**: the `Story` schema's `series` and `series_number` become nullable.
- **Contract**: the regenerated OpenAPI replaces
  `specs/001-family-reading-list/contracts/openapi.generated.json`, and the spec 009 and 013
  contract tests gain no-series cases (AC-13).

## R7 – Performance

- No new query per story: the book's story list stays one query, with one more outer join
  and an indexed column (`book_story`'s primary key starts with `book_id`).
- The perf suite gains a book page and an entry page for a 30-story anthology with no
  series, and a series page with stories, at 5,000 books (AC-16).

## R8 – Specs this amends

- **Spec 009**: AC-01 (a book's story order), AC-04 (no series is allowed, with no number).
- **Spec 013**: AC-02 (the hint), AC-10 (a missing number is allowed when the series is
  blank too), AC-11 (reworded, only for a row with a number).
