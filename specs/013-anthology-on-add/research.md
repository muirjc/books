# Research: Anthology Stories on Add a Book (spec 013)

All decisions build on what already exists:
- Add a book (`web/routes/readings.py`, `web/forms.py`);
- the spec 005 new-name prompts;
- the spec 009 story services (`services/catalog.py`: `add_new_story`, `add_existing_story`,
  `story_at`);
- the per-request rollback (`persistence/db.py`, `web/rendering.py`).

No new dependencies and no schema changes.

## R1 – Form fields for story rows

**Decision**:
- The checkbox is `anthology=yes`. Story rows are numbered from 0, and each row's fields
  carry the row number:

  | Field | Holds |
  |---|---|
  | `story_title_{i}` | the story's title |
  | `story_number_{i}` | its number in the series |
  | `story_series_name_{i}`, `story_series_id_{i}` | the series, typed or picked from the type-ahead |
  | `story_author_name_{i}`, `story_author_id_{i}` | the author, typed or picked from the type-ahead |
  | `story_id_{i}` | an existing story chosen with **Use that story** (AC-13) |

- The parser reads rows 0 to 49 that have any field present. It keeps them in order and
  renumbers them from 0, so gaps never matter.
- A new frozen `StoryRow` dataclass sits in `web/forms.py`. `AddBookForm` gains
  `anthology: bool` and `stories: list[StoryRow]`.
- Row errors use the same keys as the fields (`story_number_1`), so the existing
  `field_error` and error-summary macros work unchanged. Each message starts "Story N: …".

**Rationale**: this is the same flat, numbered-name pattern as the book's `author_name_{i}`
rows. No JSON or nested parsing is needed, and it works without JavaScript.

**Alternatives**: a JSON blob in a hidden field needs JavaScript. The array syntax
`stories[0][title]` isn't supported by Starlette form parsing.

## R2 – One author per row

**Decision**: each row has one author field. Blank means all of the book's authors. A typed
or picked name means that one author. The JSON API takes `author_ids` (a list) per story.

**Rationale**: repeatable author rows inside repeatable story rows would need two levels of
"add another" buttons without JavaScript. Most anthology stories have a single author; a
co-written story gets more authors on Edit book (spec 009 AC-16). Recorded in the spec's
Assumptions.

## R3 – Add another story and Remove without JavaScript

**Decision**:
- **Add another story** is `<button name="action" value="add_story">`.
- **Remove** is `<button name="action" value="remove_story:{i}">`, labelled "Remove story
  N".
- Both redraw the form with status 200 and write nothing, as the `draft_summary` action
  does. Field errors are not shown on a redraw.
- After **Add another story**, the new row's title has `autofocus`.
- After **Remove**, the **Stories in this book** heading has `tabindex="-1"` and
  `autofocus`, so focus lands there (AC-04, AC-05).
- At 50 rows the add button is replaced by a note (AC-06).
- An action naming a row that doesn't exist redraws the form unchanged.

**Rationale**: it reuses a proven pattern, and redraws need no session state.

## R4 – The checkbox with and without JavaScript

**Decision**:
- The server always renders the section visible, with one row.
- A small handler in `app.js` hides the section (`hidden`) when the checkbox is unticked
  on load, and toggles it on change. Rows are hidden, never cleared.
- The `aria-controls` / `aria-expanded` pair on the checkbox is not used: a plain checkbox
  followed by its section in reading order is enough.

**Rationale**: progressive enhancement. With JavaScript off, everything is visible and the
AC-08 rule (refuse rows with text when the box is unticked) stops data being silently lost.

## R5 – Checking order on save (atomicity)

**Decision**: `POST /books/add` with an anthology runs these steps in order:

1. Parse. Collect book field errors and row field errors:
   - title, number and range (`SeriesNumberIn` rules);
   - AC-11: no series anywhere;
   - AC-12: repeated pairs, where the pair is (series, number) and a blank series means
     the book's series name;
   - AC-08: the box is unticked but a row has text.
2. The spec 005 new-name prompts, for the book and the rows together (R6).
3. If any errors or prompts, redraw with 422 or 409.
4. Pre-check the rows whose series already exists. Call `story_at(series, number)`, and
   show the AC-13 choice on each taken row (409). Rows that name an existing story
   (`story_id_{i}`) are looked up; a deleted one gives a row message (409).
5. Resolve or create the book's names, then the rows' names, sharing one cache by
   lower-cased name.
6. `service.add_entry(..., stories=[...])` creates the book, then each story, then the
   entry.
7. If another member takes a story's number meanwhile, `StoryNumberTaken(index, story)` is
   raised. It shows the AC-13 choice on that row (AC-16).

Every refusal renders with status ≥ 400. `render()` sets `db_rollback`, so `get_db` rolls
back the whole request, including any authors, series, book or stories already created.
That gives AC-17 with no extra code. The API raises instead, and `get_db` rolls back on the
exception.

**Rationale**: this is the existing transaction model. Checking first gives friendly
messages, and the rollback covers races.

## R6 – New names typed in several places

**Decision**:
- Book and row names are gathered in form order: the book's authors, then the book's
  series, then each row's author, then each row's series.
- Names are grouped by lower-cased normalized name. Only the first field in each group gets
  the spec 005 prompt and its `confirm_*` / `use_*` controls; later fields in the group get
  no message.
- Row prompt controls are `confirm_story_author_{i}`, `use_story_author_{i}`,
  `confirm_story_series_{i}` and `use_story_series_{i}`.
- Confirming creates the name once. Choosing an existing similar name ("Use J.D. Robb")
  applies to every field in the group. The chosen id and catalog name are written back into
  each field, so a later redraw keeps them (spec 005 AC-06 behaviour).
- A name that exists in the catalog, or was picked from the type-ahead, needs no prompt.

**Rationale**: it meets AC-15 (one confirmation per distinct name) and keeps the spec 005
logic in one place. `new_name_prompts` is generalized to walk the list of
`(field, kind, typed name, picked id)` that a form yields.

## R7 – One service for the form and the API

**Decision**: `services/readings.add_entry` gains
`stories: Sequence[catalog_service.BookStory] = ()`. It is allowed only with `new_book`.

- `BookStory` is either `NewStory`-like, with `title`, `series_number`,
  `author_ids: list | None` and `series_id: UUID | None` (None means the book's), or an
  existing `story_id`.
- After `create_book`, for each item in order, a new story is created and linked with
  `add_new_story`, filling in the book's authors and series. An existing story is linked
  with `add_existing_story`.
- A story number conflict raises `StoryNumberTaken`, a `ConflictError` subclass that
  carries `index` and the existing story. A missing story id raises `ValidationFailed` with
  field `stories.{i}.story_id`. A missing series raises `stories.{i}.series_id`.
- The service also pre-checks `story_at` for each new item, so the API answers with the
  existing story rather than a raw constraint error.

**Rationale**: Principle VI and the constitution's "shared by api/ and web/" layer. The
service owns the defaults and the atomic order.

## R8 – JSON API shape

**Decision**:
- `ReadingEntryCreate` gains `stories: list[NewBookStory] | None`, with at most 50 items.
- `NewBookStory` holds either `story_id`, or `title` + `series_number` with optional
  `author_ids` and `series_id`.
- Model validators:
  - `stories` is refused with `book_id` (AC-26);
  - an item needs a series when `new_book.series_id` is null (AC-23);
  - pairs and story ids must be unique (AC-24).
- A conflict is the existing 409 `Problem`, with `code=story_number_taken` and
  `existing_id` set to the story (AC-25).
- The contract is a non-breaking addition: the generated `openapi.yaml` and its baseline
  are updated.

**Rationale**: it matches `StoryAdd` (spec 009) but relaxes the book defaults; omitting
`stories` is unchanged (AC-27).

## R9 – Confirmation messages

**Decision**:
- A successful anthology save adds `stories=N` to the existing redirect:
  - `/?msg=added&stories=N`;
  - `/books/add?after=…&stories=N`;
  - `/series/{id}?added=…&stories=N`.
- The pages add "with N stories" to their notice. An invalid N is ignored.
- AC-20: the duplicate-book conflict's **Add … to my list instead** form carries
  `dropped_stories=yes` when rows had text. That save redirects to the new entry's page
  with `msg=stories_not_added`, which reads "Added to your list. The stories you typed were
  not added. Add them from Edit book." The page links to Edit book.

## R10 – Performance

**Decision**: there is no new read path. The heaviest save is 50 rows: about 4 statements
per row (lookup, insert, authors, link), roughly 200 statements, well under 1 s. A perf test
times a 50-row save against the seeded 5,000-book catalog (SC-002). The redraw actions do no
database writes and read only the new-name candidates.

## R11 – Type-ahead on rows

**Decision**: the row author and series fields reuse `partials/combobox.html` with the
existing `/suggest/authors` and `/suggest/series` endpoints. Picking writes the id into the
row's hidden id field, as on the book. Without JavaScript they are plain text fields, and
the R6 prompts resolve the names.
