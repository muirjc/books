# Feature Specification: Responsive Layout for Phone, Tablet and Laptop

**Feature Branch**: `003-responsive-layout`

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "Responsive layout (bead books-bf1): scale each screen to the device it is shown on. Take advantage of the larger screen on a laptop and size appropriately for iPad and iPhone. Today every page sits in a 960px column with one breakpoint at 640px, forms are one field per row at every width, and the nav wraps to two rows on iPad. Cover My books (more columns and rows on laptop, compact rows on iPhone), the book entry and add-book forms (two columns on laptop, short fields side by side on tablet), the Open Library import table, navigation, and keep WCAG 2.2 AA (44px targets, no sideways scroll at 360px, 200% text zoom)."

## Overview

The family uses the app on three kinds of screen: iPhones, iPads and laptops. Today every
page has the same narrow layout: on a laptop most of the screen is empty margin, forms run
one field per row down a long page, and on an iPhone each book on My books takes three lines
under a tall block of filters. This feature gives each kind of screen a layout that fits it,
without changing what any page does or what data it shows.

### Screen sizes

Layouts are chosen by the width of the browser window (in CSS pixels at 100% text size),
not by the kind of device, so a narrow laptop window or an iPad in split view gets the
layout that fits its width.

| Size | Window width | Typical devices |
|---|---|---|
| **Phone** | under 640 px | iPhone (portrait), iPad in narrow split view |
| **Tablet** | 640 px to 1,023 px | iPad portrait (768–834 px), iPhone landscape, small laptop windows |
| **Laptop** | 1,024 px and wider | laptops and desktops, iPad landscape (1,024 px and up) |

Widths are measured relative to the text size, so when someone enlarges text the page
moves to the layout for a smaller screen (FR-014).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - My books fits the screen (Priority: P1)

A family member opens My books. On a laptop the list spreads across the screen and shows
more about each book (finished date and times read) with many books visible at once. On an
iPad each book stays on one line. On an iPhone each book takes two short lines, and the
sort and filter controls fold away so the list starts near the top of the screen.

**Why this priority**: My books is the page everyone opens first and most often; it is
where the wasted space on a laptop and the crowding on a phone are most noticeable.

**Independent Test**: Seed a member with 30 books, open My books at 390, 820 and 1,440 px
wide, and check the row layout, the columns shown, and how many books are visible without
scrolling.

**Acceptance Criteria**:

- **AC-01**: **Given** a laptop-width window (1,440 px), **When** a member opens My books,
  **Then** each book is one row showing title, authors and series, status, date finished and
  times read, and the list is wider than 1,200 px.
- **AC-02**: **Given** a laptop-width window, **When** My books loads, **Then** search, sort,
  status, author and series filters and the Apply button sit on one row.
- **AC-03**: **Given** a tablet-width window (768 px and 820 px), **When** My books loads,
  **Then** each book is one row showing title, authors and series, and status (as today).
- **AC-04**: **Given** a phone-width window (390 px), **When** My books loads, **Then** each
  book takes at most two lines: the title on the first, authors and series and status on
  the second.
- **AC-05**: **Given** a phone-width window and no sort or filter in use, **When** My books
  loads, **Then** the search box is shown and the other sort and filter controls are folded
  behind one "Sort and filter" control that opens them.
- **AC-06**: **Given** a phone-width window and a sort or filter already in use (for example
  from a link or after Apply), **When** My books loads, **Then** the sort and filter controls
  are shown open, so the member can see what is applied.

---

### User Story 2 - Pages use the laptop's width, and navigation fits (Priority: P1)

On a laptop, every page uses more of the screen instead of a 960 px column, while text
stays comfortable to read. The navigation (My books, Add a book, Import from Open Library,
Accounts for an admin) and the account actions (signed in as, Switch user, Sign out) fit on
one row on a laptop, and the navigation links fit on one row on an iPad.

**Why this priority**: it applies to every page and is the base the other stories build on.

**Independent Test**: Open each main page at 768, 820, 1,024 and 1,440 px wide and measure
the content width and the number of rows the header takes.

**Acceptance Criteria**:

- **AC-07**: **Given** a laptop-width window of 1,440 px, **When** any signed-in page loads,
  **Then** the page content is at least 1,200 px wide and centred; on a window wider than
  1,400 px the content stops growing at 1,320 px.
- **AC-08**: **Given** a laptop-width window, **When** any signed-in page loads, **Then** the
  site name, navigation links and account actions sit on one row, for a member and for an
  admin.
- **AC-09**: **Given** a tablet-width window (768 px and 820 px), **When** any signed-in
  page loads, **Then** all navigation links sit on one row.
- **AC-10**: **Given** any width, **When** a page with running text loads (sign in, change
  password, summary, notes), **Then** paragraphs and single text fields are no wider than
  about 75 characters of text, so lines stay readable on a wide screen.

---

### User Story 3 - Book forms use two columns on a laptop (Priority: P2)

On a laptop, the book's page shows **Book details** beside **My reading**, so the whole
form fits on one screen; Add a book does the same with the book fields beside the reading
fields. On an iPad, short fields share a row (series with number in series; status with
date finished). On an iPhone, fields stay one per row.

**Why this priority**: editing a book is now one form with ten or more fields (since
PR #17), which is a long scroll on every device today.

**Independent Test**: Open a book's page and Add a book at 390, 820 and 1,440 px and check
which fields share a row and that the form still saves.

**Acceptance Criteria**:

- **AC-11**: **Given** a laptop-width window, **When** a member opens a book's page, **Then**
  Book details and My reading are side by side, with Save below both.
- **AC-12**: **Given** a laptop-width window, **When** a member opens Add a book, **Then**
  the book fields and the reading fields are side by side, with the Add button below both.
- **AC-13**: **Given** a tablet-width window, **When** a member opens a book's page or Add a
  book, **Then** series and number in series share a row, and status and date finished share
  a row.
- **AC-14**: **Given** a phone-width window, **When** a member opens a book's page or Add a
  book, **Then** every field takes its own row.
- **AC-15**: **Given** any width, **When** a member moves through a book form with the Tab
  key, **Then** the focus order is the visual order: all book details first, then My
  reading, then Save.
- **AC-16**: **Given** a member has typed into a book form, **When** the window changes size
  (an iPad is rotated), **Then** nothing typed is lost and the layout changes to fit.

---

### User Story 4 - Import from Open Library uses the space (Priority: P3)

On a laptop the import controls (sort, filter, status for the books) sit on one row and the
works table uses the full width, so titles and author names are cut less. Tablet and phone
layouts stay as they are today.

**Why this priority**: import is used less often than the list and book pages.

**Independent Test**: Open an author's works at 1,440 px and 820 px and check the control
row and the table width.

**Acceptance Criteria**:

- **AC-17**: **Given** a laptop-width window, **When** a member opens an author's works,
  **Then** the sort, filter and status controls and their buttons sit on one row, and the
  works table is as wide as the page content.
- **AC-18**: **Given** two authors with very different titles, **When** their works are
  shown at the same width (820 px or 1,440 px), **Then** the table columns have the same
  widths (spec 002 behaviour kept).

---

### Accessibility across all sizes (applies to every story)

- **AC-19**: **Given** any page in the app, **When** it is shown at 360, 390, 768, 820,
  1,024 and 1,440 px wide, **Then** the page does not scroll sideways.
- **AC-20**: **Given** any page at any of those widths, **When** it loads, **Then** buttons,
  form controls and navigation links are at least 44 × 44 px and checkboxes at least
  24 × 24 px.
- **AC-21**: **Given** the main pages (sign in, My books, Add a book, a book's page, an
  author's works), **When** checked at phone, tablet and laptop widths, **Then** an
  automated WCAG 2.2 AA check reports no violations.
- **AC-22**: **Given** a 1,280 px wide laptop window with text enlarged to 200%, **When** any
  main page loads, **Then** it shows the tablet layout, nothing is cut off or overlapping,
  and the page does not scroll sideways.

### Edge Cases

- **Very wide screens** (2,560 px monitors): content stops growing at 1,320 px and is
  centred (AC-07).
- **Long text**: very long titles, author lists and series names wrap or are cut with "…" in
  list rows, without widening the page (AC-19); the full text is on the book's page.
- **iPad split view and Slide Over**: narrow windows get the phone or tablet layout by
  width.
- **iPhone landscape** (about 844 px wide, short): gets the tablet layout; the header must
  not take more than a quarter of the screen height, so the page content is still visible.
- **Rotation mid-edit**: layout changes, typed input is kept (AC-16).
- **Empty My books list**: the empty message and "Add your first book" link show the same
  at every width.
- **Admin**: the extra Accounts link still fits the header row on a laptop and the nav row
  on a tablet (AC-08, AC-09).
- **Personal records**: no change to who can see what; another member's entry still returns
  Not Found at every width (existing tests, Principle I).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST choose one of three layouts (phone, tablet, laptop) from the
  window width, at the boundaries in the Screen sizes table.
- **FR-002**: On laptop width, page content MUST grow with the window up to a maximum of
  1,320 px and be centred beyond that.
- **FR-003**: On laptop width, the header MUST show site name, navigation and account
  actions on one row; on tablet width, all navigation links MUST be on one row.
- **FR-004**: On phone width, the header MAY wrap, but every navigation link and account
  action MUST remain a 44 × 44 px target.
- **FR-005**: My books MUST show one row per book on tablet and laptop widths; on laptop
  width each row MUST also show date finished and times read.
- **FR-006**: My books MUST show each book in at most two lines on phone width (title;
  then authors and series with status).
- **FR-007**: On phone width, My books MUST fold sort and filter controls (other than
  search) behind one "Sort and filter" control, shown open when any sort or filter other
  than the default is in use.
- **FR-008**: On laptop width, all My books filters and Apply MUST fit on one row.
- **FR-009**: On laptop width, a book's page and Add a book MUST show the book fields and
  the reading fields in two side-by-side columns, with the submit button below both.
- **FR-010**: On tablet width, the book forms MUST pair series with number in series, and
  status with date finished, on shared rows.
- **FR-011**: On phone width, every form field MUST take its own row.
- **FR-012**: Keyboard focus order MUST follow visual order on every layout; layout changes
  MUST NOT reorder content for screen readers.
- **FR-013**: Running text and single-line text inputs MUST be limited to a readable line
  length (about 75 characters) at any width.
- **FR-014**: Layout boundaries MUST scale with the text size, so enlarged text moves a page
  to the layout for a smaller screen.
- **FR-015**: On laptop width, the import works page MUST show its controls on one row and
  the works table at the full content width; fixed column widths per author (spec 002) MUST
  be kept.
- **FR-016**: No page MUST scroll sideways at 360 px or wider, at any of the three layouts.
- **FR-017**: The feature MUST NOT change what any page does, what data it shows to whom,
  form field names, URLs, or the JSON API.
- **FR-018**: Changing window size or orientation MUST NOT reload the page or lose typed
  input.

## Data Ownership *(mandatory)*

This feature changes presentation only. It reads the same data the pages read today and
writes nothing new.

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Book title, authors, series, number | Catalog | All members | Any member (unchanged) |
| Status, date finished, times read, notes | Personal | Owner only | Owner only (unchanged) |

- **Duplication check**: N/A: no data is stored or copied.
- **Cross-user access**: unchanged; My books still shows only the signed-in member's
  entries, now with two more of that member's own fields (date finished, times read).

## AI Involvement *(mandatory)*

- **Generated content**: None
- **Approval step**: None
- **Provenance stored**: None
- **Fallback on failure**: None

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: None
- **Sent to external services**: None

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a 1,440 × 900 laptop window, My books shows at least 12 books without
  scrolling.
- **SC-002**: On a 390 × 844 iPhone screen, My books shows at least 6 books without
  scrolling.
- **SC-003**: On a 1,440 px laptop window, page content is at least 1,200 px wide (today
  960 px).
- **SC-004**: On a 1,440 px laptop window, a book's page form (book details, My reading and
  Save) is at least 40% shorter than the one-column form shown today.
- **SC-005**: Every page passes the sideways-scroll, target-size and automated WCAG 2.2 AA
  checks at 360, 390, 768, 820, 1,024 and 1,440 px, and at 200% text on a 1,280 px window.
- **SC-006**: The My books page still loads in under 1 second at p95 with 5,000 books.

## Assumptions

- The family's devices are iPhones, iPads and laptops using Safari or Chrome; the latest
  two versions of each are supported.
- iPad landscape (1,024 px and wider) is treated as a laptop; this suits its width.
- No feature is added or removed on any size; phone users can still do everything (FR-017).
- My books keeps its page size of 50 books per page; showing more per page is out of scope.
- Dark mode, print layouts and a native app are out of scope.
- The existing phone-width checks (spec 001 FR-026/SC-006, spec 002 phone tests) remain and
  are extended, not replaced.
