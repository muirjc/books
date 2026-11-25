# UI Layout Contract (spec 003)

Routes, URLs, form field names, query parameters and the JSON API are unchanged
(FR-017). The OpenAPI contract is untouched. This file fixes what each page looks like at each size;
tests in `tests/a11y/test_layout_003.py` and `tests/integration/test_layout_markup.py` check it.

## Sizes

| Size | Media query | Container |
|---|---|---|
| Phone | base (under 40em) | 100% width, 1rem side padding |
| Tablet | `min-width: 40em` | 100% width, 1rem side padding |
| Laptop | `min-width: 64em` | up to 82.5rem (1,320 px), centred, 1.5rem padding |

Everywhere: running text at most 75ch wide; stacked single-line inputs at most 40rem.

## Header (`base.html`)

| Size | Layout |
|---|---|
| Phone | wraps as needed; every link and button at least 44 × 44 px |
| Tablet | row 1: brand + account actions; row 2: all nav links on one line |
| Laptop | one row: brand, nav links, account actions ("Signed in as" visually hidden) |

## My books (`/`)

Row cells, in DOM order, inside each `li` of `.book-list.reading-list`. Only this list uses
the row layout; the series page (`.series-list`) and the summary history keep simple rows:

| Cell | Class | Content |
|---|---|---|
| Title | `.book-title` | link to `/entries/{id}` |
| Meta | `.book-meta` | authors · series link |
| Status | `.book-status` | status badge |
| Finished | `.book-finished` | "Finished 12 Mar 2026", or empty |
| Times | `.book-times` | "Read N times" when N > 1, or empty |

| Size | Row layout | Hidden cells |
|---|---|---|
| Phone | two lines: title; meta + status | finished, times |
| Tablet | one line: title, meta, status, finished | times |
| Laptop | one line: title, meta, status, finished, times | none |

Filters:

- The form keeps role `search`. Search (`#q`) is always shown.
- Sort, status, author, series, Apply and Clear sit inside `#filter-extra.filter-extra`
  (books-g39: Clear, as "Clear filters", leads the favorites line after Apply).
- The form carries `data-fold="open"` when the request has a non-default sort or any filter
  (`q`, `status`, `author_id`, `series_id`); otherwise `data-fold="closed"`.
- A `button.filters-toggle` (`type="button"`, `aria-controls="filter-extra"`,
  `aria-expanded`) is rendered `hidden`. `static/js/fold.js` shows it.
- `fold.js` loads without `defer` in `<head>`, so `html.js` is set before the first paint
  (no flash of open filters), and it doesn't depend on `app.js`.
- `[hidden]` is `display: none !important`, so the toggle stays hidden without JS.
- The phone fold applies under `not all and (min-width: 40em)`, the exact complement of
  the tablet query, so no fractional width falls between the two.

| Size | Filters |
|---|---|
| Phone, with JS | search shown; the rest folded when `data-fold="closed"`; toggle visible |
| Phone, without JS | all shown (as today) |
| Tablet | grid, wrapping as today; toggle hidden |
| Laptop | one row: search, sort, status, author, series, Apply; toggle hidden |

## Book forms (Add a book `/books/add`, a book's page `/entries/{id}`, Edit book)

- `.form-columns` wraps two groups on Add a book and a book's page:
  - Add a book: (1) book fields + summary, (2) reading fields.
  - A book's page: (1) Book details, (2) My reading.
- `.field-row` wraps the paired fields:
  - Series + Number in series (`book_fields.html`);
  - Status + Date finished (`entry_fields.html`).

| Size | Layout |
|---|---|
| Phone | one field per row |
| Tablet | one column; each `.field-row` shows its two fields side by side |
| Laptop | the two groups side by side (3 : 2), submit below both; `.field-row` pairs kept |

Focus order everywhere: group 1, group 2, submit.

## Import (`/import/authors/{key}`)

| Size | Layout |
|---|---|
| Phone | as today (stacked controls; authors column hidden) |
| Tablet | as today (wrapping controls; fixed table columns) |
| Laptop | controls on one row; table at full container width; fixed columns kept |
