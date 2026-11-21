# Research: Confirm New Author and Series Names (spec 005)

## R1. Where the check runs

- **Decision**: in `resolve_authors` and `resolve_series` (`web/routes/readings.py`), which
  Add a book, a book's page and Edit book all use. For each typed row:
  1. a chosen id whose catalog name still matches the typed name (as today) → use it;
  2. a `use_*` id (a "Use “…”" button) → use that catalog record, whatever was typed;
  3. an exact case-insensitive catalog match → today's `author_exists` / `series_exists`
     conflict ("Already in the catalog", "Use existing …");
  4. a confirmation equal to the typed name → create (a unique-index conflict here means
     someone added it meanwhile → step 3's conflict);
  5. otherwise → a `NewName` prompt for that row (kind, row index, typed name, similar
     names); nothing is created for it.
- **Rationale**: one place covers all three pages (FR-001). The services and JSON API keep
  creating names from explicit fields (FR-009).
- **Rollback**: any prompt makes the page answer 409, so `get_db` rolls back the whole
  request, including authors already created for earlier rows. No partial catalog writes
  (AC-01, AC-05).

## R2. Form fields for the choices

- **Decision**:
  - **"Add “X” as a new author"** is `<button type="submit" name="confirm_author_<i>"
    value="X">`, and the series button uses `name="confirm_series"`. A confirmed name is
    re-rendered as a hidden field of the same name, before the field's buttons, so it
    survives later pages (last value wins, as in spec 004 R2).
  - **"Use “J.D. Robb”"** is `<button type="submit" name="use_author_<i>"
    value="<author id>">`, and the series button uses `name="use_series"`.
  - **Parsing:** `AuthorRow` gains `confirmed: str` and `use_id: UUID | None`, and
    `AddBookForm` gains `series_confirmed` and `use_series_id`.
  - **Exact name only:** a confirmation counts only when `normalize_name(confirmed) ==
    row.name` (FR-005, AC-06).
- **Rationale**:
  - **No JavaScript needed:** a button sends one name/value, so it works without
    JavaScript (AC-13).
  - **"Use" can't rely on the typed name:** a chosen id only counts when the typed name
    matches it, and here it doesn't ("J DM Robb" vs "J.D. Robb"). So a "Use" choice needs
    its own field that overrides the typed name.

## R3. Similar names

- **Decision**: `similar_names(typed, candidates, limit=3, cutoff=0.75)` in
  `domain/values.py`.
  - **Loose key:** `loose_name_key(s)` applies NFKC, lower case and a leading "the " is
    dropped, then everything but letters and digits is removed.
  - **Score:** `difflib.SequenceMatcher(None, key(typed), key(candidate)).ratio()`.
  - **Authors:** scored on both name and real name, keeping the better score per author.
  - **Result:** candidates at or above 0.75, best first, ties by name, at most 3.
- **Prototype**:
  - **Typos:** on 18 typical typos (punctuation, one wrong or missing letter, a missing
    "The", spacing), the intended name ranked first every time, at a score of 0.86 or more.
    For example "J DM Robb" → "J.D. Robb" scored 0.92, and "Dresdin Files" → "The Dresden
    Files" 0.92.
  - **Genuinely new names:** these ("Janet Evanovich", "Ann Leckie", "Robert Galbraith")
    scored at most 0.53 against every name, so they get no suggestions.
  - **Conclusion:** this meets SC-002.
- **Alternatives**:
  - `pg_trgm` similarity: rejected, because it needs a database extension and a migration
    for a family-sized catalog.
  - `rapidfuzz`: rejected, because it's a new dependency (Principle VIII) and `difflib` is
    enough.
- **Data**: `persistence/catalog.author_names()` returns `(id, name, real_name)` for every
  author, and `series_names()` returns `(id, name)`. That is hundreds to a few thousand
  short rows, read only when a prompt is needed.

## R4. Showing the prompt

- **Decision**:
  - **Field error:** the prompt is added to `form.errors` on the row's field
    (`author_name_<i>` or `series_name`), with the text "“J DM Robb” is not in the family
    catalog yet". It then appears in the error summary with a link, under the field, and
    the field gets `aria-invalid` and `aria-describedby` (AC-14).
  - **Choices block:** below the field, a `partials/new_name.html` block in `.conflict`
    style lists the "Use “…”" buttons (most similar first) and the "Add “…” as a new
    author" button.
- **Rationale**: reuses the error-summary pattern every form already has, so screen
  readers get a list of what needs attention with links (WCAG 3.3.1, 3.3.3).

## R5. Combining with other problems

- **Decision**: prompts don't stop the other checks. The prompts come from a read-only
  `new_name_prompts(db, form)`, which finds each unpicked, unconfirmed, non-exact name and
  its similar names. It runs on every save, including a 422 form, so field errors and
  prompts show together (AC-11). `resolve_*` then only creates confirmed names.
  - **Add a book:** with field errors, the page answers 422 with the prompts too. Without
    them but with prompts, it answers 409, showing the prompts together with any author or
    series conflict.
  - **A book's page and Edit book:** `save_book_details` returns
    `BookSaveProblem(409, new_names=...)`.
  - **Field errors:** a missing title, or other field errors found by the same parse, show
    in the same response, because a 422 form already shows all field errors.
  - **Taken series number:** this is only known when the book is written, which happens
    after every name is settled. So it appears on the next save (AC-11 covers errors known
    together).
- **Rationale**: the book is never written until all names are settled. Partly-saved books
  can't happen.

## R6. Spec 004 interplay

- **Decision**:
  - **Keeping the choice:** the hidden `then` field already keeps **Add and add another**
    through 409 pages, and the new buttons sit in the same form, so the choice holds
    (AC-12).
  - **No second prompt:** the next-book form carries the author's catalog id, so step 1 of
    R1 applies and no prompt appears.

## R7. Testing approach

- **Unit**: the loose key, the ranking, the cutoff, real-name matches, and an SC-002 table
  of typos and their intended names.
- **Integration** (no browser), on all three pages:
  - **Rollback:** nothing is created on a prompt, and row counts are unchanged.
  - **Choices:** each choice works.
  - **Exact confirmation:** a changed name asks again.
  - **Several prompts at once.**
  - **Exact match:** gives today's conflict.
  - **Picked names:** no prompt.
  - **Book's page:** the entry is unchanged until settled.
  - **Spec 004 carry-over.**
- **Browser** (`a11y`):
  - **Flow:** with JavaScript off, click the real buttons.
  - **Accessibility:** error summary links, 44 px targets at all widths, axe at phone,
    tablet and laptop.
