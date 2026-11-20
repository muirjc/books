# Research: Responsive Layout (spec 003)

## R1. Breakpoints and units

- **Decision**: Two `min-width` media queries in `em`:
  - `40em` (640 px) starts the tablet layout;
  - `64em` (1,024 px) starts the laptop layout.

  The base styles are the phone layout, so the stylesheet stays mobile-first. Existing
  `40rem` / `40.0625rem` queries are folded into these.
- **Rationale**:
  - **Device fit:** iPhone portrait is at most 430 px, iPad portrait 744–834 px, and iPad
    landscape and laptops are 1,024 px and wider, so 640 and 1,024 separate them cleanly.
  - **Text size:** `em` in media queries follows the browser's default text size, and browser
    zoom shrinks the CSS viewport, so enlarged text moves to a smaller layout (FR-014,
    AC-22). Safari's `rem` media queries behave the same as `em`; `em` is the conventional
    choice.
- **Alternatives**:
  - Device detection by user agent: rejected, because it breaks split view and narrow
    windows.
  - Container queries: they work in current Safari and Chrome, but the page-level layout
    only needs viewport queries; not worth the added concepts.

## R2. Page width on laptop

- **Decision**: `.container` max-width becomes 82.5rem (1,320 px) from 64em, with 1.5rem side
  padding. Phone and tablet keep 100% width with 1rem padding.
- **Readable lines (FR-013)**: paragraphs, hints and notices in `main` get
  `max-width: 75ch`. Single-line text inputs and selects in stacked forms get
  `max-width: 40rem`. Fields inside the two-column grid and the filter row are already
  narrower.
- **Narrow pages:** pages that use `.narrow` (sign in, change password) keep it.
- **Rationale**: 1,320 px uses a 1,440 px laptop screen (AC-07, SC-003) without letting
  lines of text become hard to read on a 2,560 px monitor.

## R3. Header

- **Decision**:
  - **Laptop:** `header-inner` stays a flex row; the brand, nav and account actions fit on
    one row at 1,024 px.

    Estimated widths at 1,024 px (to be confirmed by the AC-08 test):

    | Item | Width |
    |---|---|
    | Brand | 190 px |
    | Four links | 520 px |
    | "Signed in as …" with two buttons | 330 px |

    That is about 1,040 px with gaps, so on laptop the "Signed in as" label shortens to the
    display name only, with "Signed in as" kept as visually hidden text. Then everything
    fits.
  - **Tablet:** the nav moves onto its own full-width row, which allows `flex-wrap: nowrap`
    for the links.
    - The link text "Import from Open Library" stays.
    - At 768 px the four links measure about 520 px, so they fit one row.
    - The brand and account actions share the first row.
  - **Phone:** unchanged wrap; every target keeps 44 px (FR-004).
- **Rationale**: meets AC-08 and AC-09 with no change to link text or order.

## R4. My books rows

- **Decision**: each `<li>` gets five cells:
  - title (link);
  - authors · series;
  - status badge;
  - date finished;
  - times read ("Read 2 times", shown only when more than 1, as today).

  The layouts use CSS grid with `grid-template-areas`:

  | Size | Rows and columns | Hidden |
  |---|---|---|
  | Phone | `"title title" / "meta status"` (two lines) | finished, times |
  | Tablet | `"title meta status finished"` | times |
  | Laptop | `"title meta status finished times"` | none |

  Cells are cut with an ellipsis, as in PR #16. DOM order equals reading order (title, meta,
  status, finished, times) at every size, so screen readers and Tab order are unaffected
  (FR-012).

  Cells hidden by `display: none` are hidden from assistive technology too. That's
  acceptable because the book's page has the same data, and the visible row never claims
  otherwise.
- **Laptop row height**: padding 0.4rem, line height 1.5, so about 40 px per row.
  At 1,440 × 900:

  | Item | Height |
  |---|---|
  | Header | 60 px |
  | h1 and Add button | 110 px |
  | One-row filters | 80 px |
  | Count | 30 px |

  That leaves about 600 px, or 15 rows (SC-001 needs 12).
- **Phone**: two lines of about 24 px plus padding come to about 62 px per row. With
  filters folded, about 280 px sits above the list, which leaves room for about 9 rows at
  844 px tall (SC-002 needs 6).
- **Alternatives**: a `<table>` for laptop only. Rejected, because two different markups
  for one list doubles template logic. The list stays a `<ul>`, as spec 001 and PR #16
  established.

## R5. Phone "Sort and filter" fold

- **Decision**: progressive enhancement:
  - **No JavaScript:** without JS the filters stay as today, all shown.
  - **Server markup:** the server renders the filter form with
    `data-fold="open"` when any sort or filter differs from the default, otherwise
    `data-fold="closed"`. It also renders a `<button type="button" class="filters-toggle"
    aria-expanded aria-controls="filter-extra" hidden>Sort and filter</button>`.
  - **What `app.js` does:** it marks `<html class="js">`, unhides the toggle, and flips
    `data-fold` and `aria-expanded` on click.
  - **What CSS does:** `.js .filters[data-fold="closed"] .filter-extra { display: none }`,
    only below 40em. At tablet and laptop widths the toggle is hidden and the extra filters
    always show.
  - **Grouping:** sort, status, author, series and Apply are wrapped in
    `<div id="filter-extra" class="filter-extra">`. Search stays outside it.
- **Rationale**: no content is lost without JS, and the open state is decided by the server
  from the query, so a link with filters opens them (AC-06). `<details>` was rejected:
  closed `<details>` content can't be shown by CSS at wider widths in Safari.
- **HTMX**: the list swap targets `#reading-list` only, so the fold state survives filtering.

## R6. Two-column book forms

- **Decision**:
  - **Laptop:** a book's page and Add a book wrap their two groups in
    `<div class="form-columns">`, a grid with `minmax(0, 3fr) minmax(0, 2fr)` columns and a
    2rem gap. The submit button sits after the grid at full width. On the book's page the
    two groups are the existing Book details and My reading sections. On Add a book they are
    the book fields plus summary, and the reading fields.
  - **Tablet:** `.field-row` (a two-column grid, `1fr 1fr`, from 40em) wraps two pairs:
    series with number in series, and status with date finished. Both partials are shared,
    so Edit book and Add a book get the pairing too.
  - **Phone:** single column (base styles).
- **Focus order**: DOM order is book fields, then reading fields, then submit, the same as
  visual order at every size (AC-15).
- **SC-004 measure**: the book page form's height at 1,440 px is compared with its height at
  390 px, where it is one column, the layout every width shows today. It must be at most
  60% of it.

## R7. Import page

- **Decision**: from 64em, `.import-controls` uses `flex-wrap: nowrap`, with fields at
  `flex: 1 1 0` and buttons `flex: none`. The table is already 100% of the container, so it
  grows with the wider container. The fixed column layout from PR #15 (from 40em) stays,
  re-expressed with the new 40em query (AC-18).

## R8. Testing approach

- **Viewports**: Playwright at 360 × 740, 390 × 844, 768 × 1024, 820 × 1180, 1,024 × 768 and
  1,440 × 900.
- **200% zoom (AC-22)**: a 640 × 450 viewport with `device_scale_factor=2` matches a 1,280 ×
  900 window at 200% browser zoom (the CSS viewport halves). Tests set the viewport per
  check with `page.set_viewport_size`. Scale factor is set on a new context for the zoom
  test.
- **Layout assertions**: element bounding boxes measure one row (same `top` within 2 px),
  hidden cells (`offsetParent === null`), widths, and how many rows lie inside the viewport.
- **Accessibility**:
  - existing `check()` (no sideways scroll, target sizes) at each width;
  - existing `assert_no_axe_violations` at phone, tablet and laptop.
- **Server-side parts** (integration, no browser): the five row cells and their text, the
  `data-fold` state for default and filtered queries, and the field order in forms.
- **Performance**: the existing perf marker test covers SC-006 unchanged.

## R9. Rotation and typed input (AC-16, FR-018)

- **Decision**: layouts are pure CSS, so a resize never reloads or re-renders. The test fills
  the title and notes, resizes from 820 × 1180 to 1,180 × 820, and checks the values are
  unchanged. This guards a property that holds today.
