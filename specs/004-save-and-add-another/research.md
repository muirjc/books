# Research: Save and Add Another (spec 004)

## R1. How the second button tells the server what to do

- **Decision**: both buttons are `<button type="submit" name="then">`, with values `list`
  (**Add to my list**, first in the form) and `another` (**Add and add another**).
  `POST /books/add` reads `then`; anything other than `another` means `list`.
- **Rationale**: works without JavaScript (FR-011). The first submit button in tree order is
  the form's default button, so Enter in a field submits as **Add to my list** (FR-010).
- **Alternatives**: a checkbox "Add another after this" (rejected: two steps, easy to leave
  on by mistake); a separate URL via `formaction` (rejected: duplicates the route and its
  error handling).

## R2. Remembering the choice across error and conflict pages

- **Decision**: the add-book form starts with `<input type="hidden" name="then"
  value="{{ chosen }}">`, where `chosen` is the `then` of the request that rendered the page
  (default `list`). The conflict's own submit buttons (Use existing author/series) sit
  before the main buttons; the separate ISBN form ("Add … to my list instead") gets the same
  hidden field.
- **Rationale**: browsers build the form data in tree order and include only the button
  that was clicked, at its own position. Starlette's `FormData.get` returns the last value
  for a repeated name. So:
  - clicking a main button: hidden `then` first, the button's `then` later → the button wins;
  - clicking a conflict button (no `then` of its own): only the hidden value → the
    original choice holds (AC-15).
- **Test**: an integration test posts both orders explicitly; an a11y (browser) test
  clicks a real conflict button, so the browser's tree-order behaviour is checked too.

## R3. Post/Redirect/Get and how the next form knows what to carry

- **Decision**: after a successful `then=another`, redirect `303` to
  `/books/add?after=<entry_id>` (the entry `service.add_entry` returns). The GET handler
  loads that entry with `service.get_entry(db, auth.account.id, entry_id)`; on
  `NotFoundError` or an unparsable id it renders the plain empty form.
- **Rationale**:
  - **Reload safety:** reloading the GET only re-reads (FR-008, AC-05).
  - **Isolation:** the entry is read through the owner-filtered data-access layer
    (Principle I); another member's id reveals nothing (FR-009).
  - **Current names:** values come from the catalog at render time, so a renamed author or
    series shows its current name (edge case).
- **Alternatives**:
  - Carry the values in query parameters: rejected; long URLs, and the form would trust
    names and ids from the URL.
  - A session flash: rejected; there's no flash store, and it is lost on reload.

## R4. The next number in the series

- **Decision**: `next_series_number(n) = floor(n) + 1` for a `Decimal` number (3 → 4,
  4.5 → 5, 0 → 1); `None` when the book has no series or no number. It is shown as a whole
  number in the field ("4", not "4.0").
- **Rationale**: matches the spec's "What carries over" table and the series-number
  validation (non-negative, up to 2 decimals). If the suggested number is taken, saving
  gives the normal books-cay conflict (AC-13); the form never checks in advance, keeping one
  source of truth (the DB constraint, Principle VI).

## R5. Building the carry-over form

- **Decision**: `carry_over_form(entry) -> AddBookForm` in `web/forms.py` sets `raw` (what
  the templates render):
  - `author_name_i` and `author_id_i` for each of the book's authors, in their stored order;
  - `series_name`, `series_id` and `series_number` (from R4) when the book is in a series;
  - `status` = the entry's status.

  Everything else is absent, so title, ISBN, date finished, summary and notes render empty.
  `book_id` is not carried, so the next save creates or picks a new book.
- **Rationale**: the templates already render from `form.raw`, including the hidden author
  and series ids. Pre-chosen ids mean saving reuses the catalog author and series and never
  creates duplicates (AC-07, AC-08, Principle II).

## R6. Confirmation and focus

- **Decision**:
  - **Confirmation:** a `<p class="notice" role="status" id="added-notice">Added
    “<a href="/entries/{id}">Title</a>” to your list.</p>` above the form.
  - **Focus and announcement:** on the Title combobox, `autofocus` and
    `aria-describedby="added-notice"` (added to any error or hint ids already there).
- **Rationale**:
  - **Focus without JavaScript:** `autofocus` puts focus in Title (AC-03, FR-005).
  - **Read on load:** a `role="status"` region is not reliably read when the page first
    loads, but the description of the focused field is. So screen readers read the
    confirmation as Title gets focus (AC-02).
  - **Plain page:** autofocus only on the carry-over page; the plain Add a book page is
    unchanged.

## R7. Layout of the two buttons

- **Decision**: wrap the buttons in `<div class="form-actions">`, a flex row with
  `flex-wrap: wrap` and a 0.75rem gap. On a phone they wrap to two full-width rows when they
  don't fit, and they sit side by side on tablet and laptop. Both keep the 44 px minimum
  height already set for buttons.
- **Rationale**: AC-17 (no sideways scroll at 360 px, 44 × 44 targets). DOM order puts
  **Add to my list** first, matching the visual and Tab order.
