# Feature Specification: Upcoming Books

**Feature Branch**: `007-upcoming-books`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "Upcoming books (bead books-a9y, from the books-0wi discussion).
A catalog book can have an optional expected release date, entered by hand (no lookups).
While that date is in the future the book shows 'Coming <date>' wherever it appears. A
member can tick 'Pre-ordered' on their own reading entry. My books gets an Upcoming filter,
sorted by release date, soonest first, and there is a separate Upcoming page. For 30 days
after a release date, My books shows a 'Now out: <title>' notice for books on the member's
list, worked out each time the page is viewed (nothing stored). Other members' entries stay
private. Must work without JavaScript and meet WCAG 2.2 AA and the spec 003 layouts."

## Overview

Family members follow series and authors, and often know a new book is coming months
before it is out. Today the app has nowhere to put a book that isn't released yet, and
nothing reminds a member when it arrives.

This feature adds:

- **Release date on a catalog book** (optional, typed by hand; the app never looks it up).
  While the date is in the future, the book shows **Coming 3 Mar 2027**.
- **Pre-ordered** on a member's own entry, a private tick.
- **An Upcoming filter on My books**, soonest first.
- **An Upcoming page**: my upcoming books, then other upcoming books in the family
  catalog that aren't on my list, each with **Add to my list**.
- **A "Now out" notice on My books** for 30 days from a book's release date, for books on
  my list that I still want to read. It is worked out when the page is shown; nothing is
  stored and nothing needs dismissing.

"Today" is the server's date, the same date the app already uses to stop a finished date
being in the future.

### Example

Today is 21 Nov 2026. Alice's list:

| Book | Release date | Alice's entry | Shows |
|---|---|---|---|
| Twelve Months | 3 Mar 2027 | Want to read, Pre-ordered | Coming 3 Mar 2027 · Pre-ordered |
| Mirror Mirror | 1 Jun 2027 | Want to read | Coming 1 Jun 2027 |
| The Olympian Affair | 7 Nov 2026 | Want to read, Pre-ordered | Notice: "Now out: The Olympian Affair (pre-ordered)" |
| Storm Front | 1 Apr 2000 | Finished | nothing new |

The family catalog also has "Wind and Truth" (release date 6 Dec 2026), on Ben's list
only. Alice's Upcoming page shows Twelve Months and Mirror Mirror under **On my list**, and
Wind and Truth under **Also coming in the family catalog**, with **Add to my list**. It
gives no sign that Ben has it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record a release date and see "Coming" (Priority: P1)

A member adds or edits a book and gives it an expected release date. Until that day, the
book shows "Coming <date>" wherever it is listed.

**Why this priority**: everything else in the feature depends on books having a release
date.

**Independent Test**: Add a book with a future release date, then check My books, its
series page and its entry page all show "Coming <date>"; change the date to a past one and
check the label goes.

**Acceptance Criteria**:

- **AC-01**: **Given** Add a book, **When** the member enters a release date and saves,
  **Then** the catalog book stores that date; the field is optional and blank by default.
- **AC-02**: **Given** Edit book for a catalog book, **When** the member sets, changes or
  clears the release date and saves, **Then** the book's release date is updated for the
  whole family, as other book details are today.
- **AC-03**: **Given** a release date that isn't a real calendar date, **When** the member
  saves, **Then** the form is shown again with an error on the release date field and
  nothing is saved, as with other field errors today.
- **AC-04**: **Given** a book whose release date is after today, **When** it is shown on My
  books, the series page or its entry page, **Then** it shows "Coming <date>" (for example
  "Coming 3 Mar 2027") in text next to its status.
- **AC-05**: **Given** a book whose release date is today or earlier, or which has none,
  **When** it is shown, **Then** no "Coming" label appears; its entry page shows "Released
  <date>" when it has a date.
- **AC-06**: **Given** Add a book started from a catalog book (spec 006), **When** that book
  has a release date, **Then** the chosen book's details include "Coming <date>" if the
  date is in the future.

---

### User Story 2 - Pre-ordered (Priority: P2)

A member ticks Pre-ordered on their own entry, so they remember they've already ordered it.

**Why this priority**: useful, small, and only meaningful once books have release dates.

**Independent Test**: Tick Pre-ordered on an entry for an upcoming book, check it shows on
My books and the entry page, and that another member sees nothing of it.

**Acceptance Criteria**:

- **AC-07**: **Given** Add a book or the entry's edit form, **When** the member ticks
  **Pre-ordered** and saves, **Then** their entry records it; unticking and saving clears
  it. It is off by default.
- **AC-08**: **Given** an entry marked Pre-ordered whose book is upcoming or within its Now
  out period (AC-14), **When** My books, the entry page, the series page or the Upcoming
  page shows it, **Then** "Pre-ordered" appears in text next to the Coming label or in the
  notice. Outside that time the tick is kept but not shown in lists; the entry form still
  shows it.
- **AC-09**: **Given** Alice marked her entry Pre-ordered, **When** Ben views the same
  catalog book anywhere, **Then** nothing shows whether Alice has it, has pre-ordered it, or
  how many members have.

---

### User Story 3 - Upcoming on My books and the Upcoming page (Priority: P1)

A member sees what's coming: an Upcoming filter on My books, and an Upcoming page that also
shows other upcoming books in the family catalog.

**Why this priority**: this is the "what's coming" view the request is for.

**Independent Test**: With upcoming and released books on the list and in the catalog,
turn on the Upcoming filter and open the Upcoming page, and check the books and order.

**Acceptance Criteria**:

- **AC-10**: **Given** My books, **When** the member turns on **Upcoming only**, **Then** the
  list shows only their books whose release date is after today, soonest first (ties by
  title), and the count reflects it. Search and the author, series and status filters
  still apply on top.
- **AC-11**: **Given** the Upcoming filter is on, **When** the member pages, searches or
  changes another filter, **Then** it stays on (like other filters today), and **Clear**
  turns it off.
- **AC-12**: **Given** the Upcoming page, **When** the member opens it from the main
  navigation, **Then** it shows **On my list**: their entries whose book is upcoming,
  soonest first, each with title, authors, series, Coming date, status and Pre-ordered;
  then **Also coming in the family catalog**: catalog books with a future release date
  that are not on their list, soonest first, each with **Add to my list** (which opens Add
  a book from that book, as spec 006 does).
- **AC-13**: **Given** no upcoming books on the member's list or in the catalog, **When**
  they open the Upcoming page, **Then** each empty section says so ("Nothing on your list is
  coming up." / "Nothing else in the family catalog is coming up."), and the page offers
  **Add a book**.

---

### User Story 4 - "Now out" notice (Priority: P1)

When a book a member is waiting for comes out, My books tells them, for 30 days.

**Why this priority**: the reminder is the point of recording a release date.

**Independent Test**: With a book on the list released 5 days ago and another 40 days ago,
open My books and check only the first gives a notice; change the clock and check it
appears on release day and goes after 30 days.

**Acceptance Criteria**:

- **AC-14**: **Given** a book on the member's list with status **Want to read** whose
  release date is today or up to 29 days before today, **When** they open My books,
  **Then** a notice near the top says "Now out: <title>", linking to their entry, with
  "(pre-ordered)" when the entry is Pre-ordered. Several such books are listed in one
  notice, most recent release first.
- **AC-15**: **Given** the release date is 30 or more days before today, or after today,
  **When** they open My books, **Then** that book is not in the notice.
- **AC-16**: **Given** the book's entry is Reading or Finished, **When** they open My books,
  **Then** that book is not in the notice.
- **AC-17**: **Given** no books qualify, **When** they open My books, **Then** there is no
  notice and nothing empty is left in its place.
- **AC-18**: **Given** Ben has a book released yesterday on his list, **When** Alice, who
  doesn't have it, opens My books, **Then** her notice doesn't mention it.

---

### User Story 5 - Usable everywhere (Priority: P2)

**Acceptance Criteria**:

- **AC-19**: **Given** the Upcoming page, My books with the notice and the filter on, and
  the forms with the new fields, **When** they are checked at phone, tablet and laptop
  widths (spec 003), **Then** there is no sideways scroll, every link and control is at
  least 44 × 44 CSS px, and axe reports no WCAG 2.2 AA violations.
- **AC-20**: **Given** JavaScript is off, **When** the member records a release date, ticks
  Pre-ordered, uses the Upcoming filter and opens the Upcoming page, **Then** everything
  works as with JavaScript on.
- **AC-21**: **Given** a screen reader user, **When** My books loads with a notice, **Then**
  the notice is announced as a status message, and the Coming, Released and Pre-ordered
  labels are text, not colour or icon alone.

### Edge Cases

- **Release date moved later:** the book becomes upcoming again; any notice for it goes.
- **Release date moved earlier, into the past 30 days:** the notice appears from the next
  view.
- **Finished before release** (an advance copy): allowed; a Finished entry never gets the
  notice (AC-16). The existing rule that a finished date can't be in the future still holds.
- **A book with no date:** never upcoming, never in the notice, never on the Upcoming page.
- **Another member's entry:** never shown or counted (AC-09, AC-18). Opening another
  member's entry by link still gives 404 (Principle I, unchanged).
- **Day boundary:** "today" is the server's date, as for the finished-date check.
- **Long lists:** the Upcoming page lists everything without paging; see SC-002.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A catalog book MUST be able to carry an optional release date, set, changed or
  cleared on Add a book and Edit book by any member, and validated as a real date.
- **FR-002**: A book whose release date is after today MUST show "Coming <date>" on My
  books, the series page, its entry page, the Upcoming page and the chosen-book display on
  Add a book. A past release date MUST show as "Released <date>" on the entry page only.
- **FR-003**: A reading entry MUST be able to carry a private Pre-ordered flag, off by
  default, set on Add a book and the entry's edit form, shown while the book is upcoming or
  in its Now out period.
- **FR-004**: My books MUST offer an Upcoming only filter showing only the member's books
  with a future release date, soonest first, combinable with the existing search and
  filters, kept across pages and cleared by Clear.
- **FR-005**: There MUST be an Upcoming page in the main navigation with the member's
  upcoming books, then other upcoming catalog books not on their list with Add to my list,
  each section soonest first.
- **FR-006**: My books MUST show a "Now out" notice listing each book on the member's list
  with status Want to read whose release date is from 29 days before today up to today,
  computed on each view and not stored.
- **FR-007**: No page or API response MUST reveal another member's entries, statuses,
  Pre-ordered flags or counts.
- **FR-008**: The JSON API MUST expose the book's release date and the entry's Pre-ordered
  flag for reading and writing, and an upcoming-only filter on the member's reading list,
  with additive, non-breaking changes.
- **FR-009**: All of the above MUST work without JavaScript and meet WCAG 2.2 AA and the
  spec 003 layouts.

### Key Entities

- **Book (catalog)**: gains an optional release date.
- **Reading entry (personal)**: gains a Pre-ordered flag.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Release date | Catalog | All members | Any member (as other book details) |
| Pre-ordered | Personal | Owner only | Owner only |
| "Now out" notice, Upcoming lists | Derived | Owner only (their entries); catalog part all members | Not stored |

- **Duplication check**: the release date lives on the catalog book only; no entry copies
  it. Pre-ordered is personal and lives on the entry (Principle II).
- **Cross-user access**: none. The "Also coming in the family catalog" section lists
  catalog books only, chosen as "not on my list" through my own entries; it never reads or
  reveals another member's entries.

## AI Involvement *(mandatory)*

- **Generated content**: None.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: the Pre-ordered flag on the member's own entries; the
  minimum needed to show it.
- **Sent to external services**: None. Release dates are typed by hand; nothing is looked
  up.

## API Changes *(include if feature changes the JSON API)*

- **New endpoints**: None required; the existing book and reading-entry resources gain
  fields and the reading list gains a filter (details in the plan's contracts).
- **Breaking changes**: None. New fields are optional on input and added on output.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A member can record an upcoming book with its release date and Pre-ordered in
  one Add a book save.
- **SC-002**: My books (with the notice, and with Upcoming only on) and the Upcoming page
  load in under 1 s at p95 with 5,000 books in the catalog, 5,000 entries for the viewer
  and 200 upcoming books.
- **SC-003**: No test or page view shows another member's reading data on the Upcoming
  page, in the notice, or anywhere a release date or Pre-ordered appears.

## Assumptions

- **Window of 30 days:** decided by the user (2026-11-21). The release day is day 1; the
  notice shows through day 30 and is gone from day 31.
- **Want to read only for the notice:** a member reading or finished with the book already
  has it.
- **No dismiss button:** the notice goes by itself after 30 days or when the member changes
  the status; nothing extra is stored.
- **Upcoming only uses its own order:** with the filter on, the list is soonest first
  whatever Sort by says, as the request asks; the page says so next to the filter.
- **Add to my list from the Upcoming page** opens Add a book from the book (spec 006) and
  returns to My books afterwards, as a plain Add a book does; returning to the Upcoming page
  is out of scope.
- **Date only, no "month/year" or "TBA":** an approximate date is entered as a best guess
  and edited later.
- **No series index or reminders by email/push:** out of scope.
