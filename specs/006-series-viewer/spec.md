# Feature Specification: Series Viewer

**Feature Branch**: `006-series-viewer`

**Created**: 2026-11-21

**Status**: Implemented

**Input**: User description: "Series viewer (bead books-56w, from the books-0wi discussion):
the series page lists every catalog book in the series in number order, each with the
member's own status or 'Not on my list' plus Add; shows numbering gaps; other members'
entries stay private."

## Overview

Today a series page (reached from a book's series link) shows only the books from that
series on the member's own list. A member catching up on a series can't see which books
they haven't got, or whether the family catalog is missing some.

This feature turns the series page into a view of the whole series:

- **Every catalog book in the series**, in number order, unnumbered books last.
- **The member's own status on each:** Want to read, Reading, or Finished (with the date),
  linking to their entry. A book not on their list says **Not on my list** with an **Add
  to my list** link.
- **Gaps:** a missing whole number between 1 and the highest number in the series shows as
  "#4 · Not in the family catalog yet", with an **Add #4** link.
- **Progress:** "You've finished 5 of 9 books in this series."
- **Back to the series:** adding a book from the series page returns to the series page,
  so a member can work down the series.

Other members' reading stays private (Principle I): the page shows the shared catalog and
the viewer's own entries, nothing else.

### Example

The Dresden Files, for a member who has finished #1–#3 and is reading #5, with #4 and #6 in
the catalog and #7 missing, and a short story collection with no number:

| Row | Shows |
|---|---|
| #1 Storm Front | Finished · 3 Mar 2025 |
| #2 Fool Moon | Finished |
| #3 Grave Peril | Finished |
| #4 Summer Knight | Not on my list · **Add to my list** |
| #5 Death Masks | Reading |
| #6 Blood Rites | Not on my list · **Add to my list** |
| #7 | Not in the family catalog yet · **Add #7** |
| #8 Proven Guilty | Want to read |
| Side Jobs (no number) | Not on my list · **Add to my list** |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the whole series with my place in it (Priority: P1)

A member opens a series and sees every book the family catalog has in it, in order, with
their own status on each, so they can tell at a glance what they've read and what's next.

**Why this priority**: this is the request: browse a series as a whole, not just my books.

**Independent Test**: With a series of catalog books, some on the member's list in
different statuses and some on nobody's list, open the series page and check every book
appears in order with the right status.

**Acceptance Criteria**:

- **AC-01**: **Given** a series whose catalog books are partly on the member's list,
  **When** they open the series page, **Then** every catalog book in the series is listed,
  numbered books in ascending number order, then unnumbered books by title.
- **AC-02**: **Given** a book on the member's list, **When** the series page shows it,
  **Then** its row shows their status (Want to read, Reading, or Finished, with the date
  finished when there is one), and the title links to their entry.
- **AC-03**: **Given** a book in the series that is not on the member's list (whether or
  not another member has it), **When** the series page shows it, **Then** its row says
  **Not on my list**, and nothing on the page shows whether, or how, any other member is
  reading it.
- **AC-04**: **Given** the member has finished some books in the series, **When** they open
  it, **Then** the page says "You've finished N of M books in this series", where M counts
  the catalog books listed (gaps are not books).
- **AC-05**: **Given** a series id that doesn't exist, or a malformed one, **When** the
  member opens it, **Then** they get Not Found, as today.
- **AC-06**: **Given** a series with no catalog books (all removed or renumbered away),
  **When** the member opens it, **Then** the page says the family catalog has no books in
  this series yet and offers **Add a book to this series**.

---

### User Story 2 - Add a missing book from the series page (Priority: P1)

From a row saying **Not on my list**, the member adds that catalog book to their list. From
a gap row, they add a new book at that number. Either way they come back to the series
page afterwards.

**Why this priority**: seeing what's missing is only half useful if adding it means going
off to Add a book and retyping the series.

**Independent Test**: From the series page, add a catalog book not on the list and a book
at a gap, and check each lands on the list and the member returns to the series page.

**Acceptance Criteria**:

- **AC-07**: **Given** a row saying **Not on my list**, **When** the member chooses **Add
  to my list**, **Then** Add a book opens with that catalog book already chosen (its
  title, authors, series and number shown, and nothing typed creates a new book), with
  status **Want to read**.
- **AC-08**: **Given** Add a book opened from the series page, **When** the member saves
  with **Add to my list**, **Then** the book is added to their list and they return to the
  series page with a confirmation naming the book, where its row now shows their status.
- **AC-09**: **Given** a gap row "#7 · Not in the family catalog yet", **When** the member
  chooses **Add #7**, **Then** Add a book opens with the series and number 7 filled in and
  the other book fields empty; saving it returns to the series page, where #7 now shows the
  new book.
- **AC-10**: **Given** Add a book opened from the series page, **When** the save meets a
  field error, a conflict or a new-name prompt (spec 005), **Then** it is handled exactly
  as on Add a book today, and after it is settled the member still returns to the series
  page.
- **AC-11**: **Given** Add a book opened from the series page, **When** the member uses
  **Add and add another** (spec 004), **Then** it behaves as today (the next-book form),
  not a return to the series page.
- **AC-12**: **Given** a link to Add a book naming a catalog book, a series or a return
  page that doesn't exist or is malformed, **When** it is opened, **Then** the plain Add a
  book form opens and saving goes to My books as usual; a return address is only ever a
  series page, never an arbitrary address.
- **AC-13**: **Given** the member opens **Add to my list** for a book, **When** they
  already have that book on their list by then (added in another tab), **Then** saving
  gives today's "already on your list" handling and nothing is duplicated.

---

### User Story 3 - See gaps in the numbering (Priority: P2)

Where the catalog is missing a whole number in the series, a row says so, so the member
knows the family hasn't entered that book yet.

**Why this priority**: useful for keeping the catalog complete, but the page works without
it.

**Independent Test**: In a series numbered 1, 2, 4, 6.5, open the series page and check
rows for #3 and #5, and none for 6 or fractions.

**Acceptance Criteria**:

- **AC-14**: **Given** a series with books numbered 1, 2, 4 and 6.5, **When** the series
  page shows it, **Then** gap rows appear for #3, #5 and #6, each in its place in the order
  (#6 before #6.5), and none above 6. A gap is a whole number from 1 up to the highest
  number's whole part that no book has exactly; fractional numbers never make gaps.
- **AC-15**: **Given** a series with no numbered books, **When** the page shows it, **Then**
  there are no gap rows.
- **AC-16**: **Given** a series whose highest number is very large (for example a book at
  #500), **When** the page shows it, **Then** consecutive missing numbers are collapsed into
  one row, such as "#8–#499 · Not in the family catalog yet", so the page stays short, and
  that row offers **Add #8**.

---

### User Story 4 - Usable everywhere (Priority: P2)

The series page meets the same accessibility and layout rules as every other page.

**Acceptance Criteria**:

- **AC-17**: **Given** the series page with books in each state and a gap, **When** it is
  checked at phone, tablet and laptop widths (spec 003), **Then** there is no sideways
  scroll, every link is at least 44 × 44 CSS px, and axe reports no WCAG 2.2 AA violations.
- **AC-18**: **Given** a screen reader user, **When** they read a row, **Then** the number,
  title, authors and status are read in that order, and the status is in text, not colour
  alone.
- **AC-19**: **Given** JavaScript is off, **When** the member uses the series page and its
  Add links, **Then** everything works as with JavaScript on.

### Edge Cases

- **Another member's entry:** the page never shows other members' statuses, dates, notes or
  counts (AC-03). Opening another member's entry through a link still gives 404 (Principle
  I, unchanged).
- **Two books with the same number:** can't happen (spec 001 AC-19, series numbers are
  unique within a series).
- **A book removed from the series meanwhile:** the page reflects the catalog when it is
  loaded; Add a book uses the book as it is when saved.
- **A book the member removed from their list:** shows **Not on my list** again.
- **Long series** (hundreds of books): the page lists them all without paging; see SC-002.
- **Read more than once:** the status shown is the entry's current status; "read N times"
  is not shown here (it is on the book's page).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The series page MUST list every catalog book in the series: numbered books by
  ascending number, then unnumbered books by title (case-insensitive).
- **FR-002**: Each row MUST show the number (or "No number"), title and authors, and the
  viewer's own status: their entry's status (with date finished, if any) linking to the
  entry, or **Not on my list** with **Add to my list**.
- **FR-003**: The page MUST NOT show or reveal any other member's reading entry, in any
  form, including counts.
- **FR-004**: The page MUST show "You've finished N of M books in this series", counting
  the viewer's Finished entries among the listed books.
- **FR-005**: The page MUST show a gap row for each missing whole number from 1 to the
  highest number's whole part, with consecutive missing numbers collapsed into one row
  when there are more than three in a run, each with **Add #n** for the first number.
- **FR-006**: Add a book MUST accept a catalog book to start from, opening with that book
  chosen and status Want to read; and a series plus number to start from, opening with the
  series and number filled in. Unknown or malformed values MUST be ignored.
- **FR-007**: Add a book opened from a series page MUST return to that series page after a
  successful **Add to my list**, with a confirmation naming the book. The return address
  MUST be built by the server from a series id, never taken as a free-form address.
- **FR-008**: Adding from the series page MUST use today's Add a book checks, conflicts and
  new-name prompts unchanged, and keep the return to the series page through them.
- **FR-009**: The series page and the Add links MUST work without JavaScript and meet
  WCAG 2.2 AA and the spec 003 layouts.
- **FR-010**: The JSON API is unchanged.

### Key Entities

No new entities or stored data. The page combines the shared catalog's books in a series
with the viewer's own reading entries.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Series, its books, numbers, authors | Catalog | All members | Any member (unchanged) |
| Status and date finished on each row | Personal | Owner only | Owner only (via Add a book, unchanged) |
| "Finished N of M" | Derived from personal | Owner only | Not stored |

- **Duplication check**: nothing is copied; the page reads catalog and entries live.
- **Cross-user access**: none. Entries are read through the existing per-member data access
  (Principle I); other members' entries are never queried for this page.

## AI Involvement *(mandatory)*

- **Generated content**: None.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: None.
- **Sent to external services**: None.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a book's page, a member can see which books of its series they haven't
  read and add one, in at most three actions (open series, Add to my list, save).
- **SC-002**: The series page loads within the existing page budget (under 1 s at p95)
  for a 100-book series in a 5,000-book catalog with 5,000 entries for the viewer.
- **SC-003**: No test or page view shows any other member's reading data on the series
  page.

## Assumptions

- **Default status Want to read** when adding from the series page: a book the member
  hasn't got is most often one they mean to read. They can change it before saving.
- **Gap collapsing at more than three:** short runs (#3, #4, #5) are clearer as single
  rows; longer runs are one row so a stray large number doesn't make the page huge.
- **No series index page:** the series page is reached as today, from a book's series link
  and from Edit series. A browse-all-series page is out of scope.
- **Upcoming books** (books-a9y, spec 007) will later add release dates to these rows; this
  spec does not.
