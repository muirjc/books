# Feature Specification: Stories in Collections

**Feature Branch**: `009-collection-stories`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "How do we handle books that are made up of multiple short
stories that fit into different points of the series timeline? The book that is entered
actually contains the 1.5, 2.5 and 6.5 stories." (bead books-tft). Clarified with the user
on 2026-11-22: each story is its own catalog item, contained in one or more books; a story
may share a series number with a standalone book.

## Overview

A book has one series and one number. A short story collection doesn't fit: *Side Jobs*
holds Dresden Files stories that belong at #1.5, #2.5, #6.5 and more. Today a member picks
one number (or none), and the series page can't show where the stories sit in the reading
order.

This feature adds **stories** to the shared catalog:

- A **story** has a title, authors, and a place in a series (series and number).
- A story is **contained in** one or more catalog books. The same story collected in two
  books is one story, listed in both.
- The **series page** lists each story at its number, with the book(s) it's in, alongside
  the series' books.
- A member's place in a story comes from their own entries: a story is **finished** when
  they have finished a book that contains it. Nothing personal is stored per story.

The book itself is unchanged: a collection keeps its own series and number (often none), and
a member adds the collection to their list as any other book.

### Example

The Dresden Files for a member who has finished *Side Jobs* and *Storm Front*, and is
reading *Fool Moon*:

| Row | Shows |
|---|---|
| #1 Storm Front | Finished · 3 Mar 2025 |
| #1.5 Restoration of Faith *(story)* | In *Side Jobs* · Finished |
| #2 Fool Moon | Reading |
| #2.5 Publicity and Advertising *(story)* | In *Side Jobs* · Finished |
| #3 | Not in the family catalog yet · **Add #3** |
| … | |
| #6.5 Something Borrowed *(story)* | In *Side Jobs* · Finished |
| Side Jobs (no number) | Finished · Contains #1.5, #2.5, #6.5 |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record the stories in a collection (Priority: P1)

A member opens a collection's book page and adds its stories, each with a title and its
series number. The authors and series default to the book's.

**Why this priority**: nothing else works until stories can be recorded.

**Independent Test**: On Edit book for *Side Jobs*, add stories at #1.5, #2.5 and #6.5 of
The Dresden Files; check the book page lists them in number order and they are stored once
each.

**Acceptance Criteria**:

- **AC-01**: **Given** a catalog book, **When** a member opens Edit book, **Then** a
  **Stories in this book** section lists its stories (series, number, title; by series name,
  then number) and offers **Add a story**.
- **AC-02**: **Given** Add a story on a book, **When** the form opens, **Then** the series
  is filled with the book's series (if any) and the authors with the book's authors; the
  member types the title and number, and may change the series and authors.
- **AC-03**: **Given** a valid title, series and number, **When** the member saves, **Then**
  the story is added to the catalog and to this book, and the member returns to Edit book
  with a confirmation naming the story.
- **AC-04**: **Given** Add a story, **When** the title is blank, the number is missing or out
  of range (the same 0–999.99 rule as book numbers), or no series is given, **Then** the
  story is refused with a message beside each field, and what was typed is kept.
- **AC-05**: **Given** a series and number already held by a story (say #2.5 *Publicity and
  Advertising*, in *Side Jobs*), **When** a member adds a story at that series and number to
  another book, **Then** nothing is saved yet; the page names the existing story and the
  book(s) it's in, and offers **Add that story to this book** or changing the number. A
  second story at the same series and number is never created.
- **AC-06**: **Given** a series and number held by a **book** (say a standalone edition of
  #2.5), **When** a member adds a story at that number, **Then** it is allowed: a story and a
  book may share a number.
- **AC-07**: **Given** a new series or author name typed in Add a story, **When** the member
  saves, **Then** the spec 005 new-name prompt applies, as on Add a book.
- **AC-08**: **Given** a book with stories, **When** a member views their entry for it,
  **Then** the entry page lists the stories (number, series, title), each linking to the
  series page, with a link to edit them.

---

### User Story 2 - See stories in the series reading order (Priority: P1)

A member opens a series and sees its stories at their numbers among the books, with the
book each is in and the member's own progress.

**Why this priority**: placing the stories in the timeline is the reason for the feature.

**Independent Test**: With *Side Jobs* holding #1.5, #2.5 and #6.5 and the member having
finished it, open the Dresden Files page and check each story row sits in number order with
"In *Side Jobs* · Finished".

**Acceptance Criteria**:

- **AC-09**: **Given** a series with books and stories, **When** a member opens its series
  page, **Then** stories appear as rows in number order among the numbered books, each
  marked as a story and naming the book(s) it's in, each book name linking to the member's
  entry for that book if they have one, or else to Add a book with that book chosen
  (spec 006).
- **AC-10**: **Given** a story and a book with the same number, **When** the page shows
  them, **Then** both rows appear at that number, the book first.
- **AC-11**: **Given** a story, **When** the page shows its status, **Then** it is the
  member's own progress through the books that contain it: **Finished** if they finished
  any of them (with that date), else **Reading** if they are reading one, else **Want to
  read** if one is on their list, else **Not on my list** with **Add *<book>* to my list**
  for each containing book.
- **AC-12**: **Given** a story at a whole number (say #3), **When** the page works out
  gaps, **Then** #3 is not a gap. A story at a fractional number, like a book at one, ends a
  run of gap rows so it keeps its place (spec 006 AC-14, AC-16).
- **AC-13**: **Given** a series with stories, **When** the page shows progress, **Then** it
  says "You've finished N of M books and K of L stories in this series"; with no stories it
  reads as today.
- **AC-14**: **Given** a collection book in the series, **When** its row is shown, **Then**
  it also says which story numbers it contains in this series ("Contains #1.5, #2.5,
  #6.5").
- **AC-15**: **Given** another member has finished *Side Jobs* and the viewer hasn't got it,
  **When** the viewer opens the series, **Then** the story rows say **Not on my list**, and
  nothing on the page shows any other member's reading.

---

### User Story 3 - Edit, move and remove stories (Priority: P2)

A member fixes a story's title, number, series or authors, adds an existing story to
another collection it appears in, or takes a story out of a book.

**Why this priority**: mistakes and re-collections happen, but recording comes first.

**Independent Test**: Edit a story's number from 2.5 to 2.6; add it to a second book; remove
it from the first; remove it from the last book and confirm it is gone.

**Acceptance Criteria**:

- **AC-16**: **Given** a story, **When** a member edits its title, authors, series or
  number, **Then** the change is saved for every book it's in. Moving it to a series and
  number held by another story is refused with a message naming that story, nothing saved.
- **AC-17**: **Given** Add a story on a book, **When** the member chooses an existing story
  (by series and number, AC-05, or by a title suggestion), **Then** the story is added to
  this book as well; it is not copied. Adding a story the book already contains does
  nothing and says so.
- **AC-18**: **Given** a story in two books, **When** a member chooses **Remove from this
  book** on one, **Then** after a confirmation the story is no longer in that book and stays
  in the other.
- **AC-19**: **Given** a story in only this book, **When** a member removes it, **Then** the
  confirmation says the story will be deleted from the catalog, and after confirming it is
  gone.
- **AC-20**: **Given** an author whose only catalog works are stories, **When** a member
  tries to delete the author (spec 008), **Then** it is refused as today for an author with
  books, and the author is not listed under Authors with no books.
- **AC-21**: **Given** a story id or book id that doesn't exist, or a story not in the given
  book, **When** a member opens or posts to its pages, **Then** they get Not Found.

---

### User Story 4 - Find a collection by a story's title (Priority: P3)

Typing a story's title on Add a book suggests the collection that contains it.

**Why this priority**: helpful, but members usually know the collection's title.

**Acceptance Criteria**:

- **AC-22**: **Given** *Side Jobs* contains *Restoration of Faith*, **When** a member types
  "Restoration" in the title box on Add a book, **Then** *Side Jobs* is suggested, labelled
  with the matching story ("contains *Restoration of Faith*"); choosing it adds *Side Jobs*.

---

### User Story 5 - Usable everywhere (Priority: P2)

**Acceptance Criteria**:

- **AC-23**: **Given** the story section, the story forms, the confirmation pages and a
  series page with story rows, **When** each is checked at phone, tablet and laptop widths
  (spec 003), **Then** there is no sideways scroll, every control is at least 44 × 44 CSS
  px, and axe reports no WCAG 2.2 AA violations.
- **AC-24**: **Given** a screen reader user on the series page, **When** they read a story
  row, **Then** the number, the word "Story", the title, the containing book(s) and the
  status are read in that order, with the status in text.
- **AC-25**: **Given** JavaScript is off, **When** a member adds, edits and removes stories,
  **Then** everything works as with JavaScript on.
- **AC-26**: **Given** the JSON API, **When** a client lists, adds, links, edits and removes
  stories, and lists a book's stories, **Then** the responses match the published
  contract.

### Edge Cases

- **Another member's entries:** story statuses come only from the viewer's own entries
  (AC-11, AC-15). Opening another member's entry from a story row is impossible: the row
  links only to the viewer's own entries.
- **Two members add the same story at once:** the database refuses the second; that member
  sees the AC-05 choice.
- **A story whose series differs from its book's:** allowed (a Dresden story in an anthology
  of many authors). It shows on its own series' page; the book shows on its own series'
  page, if any.
- **A story in a book that is in the same series at the same number:** allowed (AC-06,
  AC-10); both rows show.
- **Removing a collection from my list:** the catalog book and its stories stay; the story
  rows show **Not on my list** again.
- **Re-reads:** a story's status follows the containing entry's current status; "read N
  times" isn't shown for stories.
- **Stale pages:** story forms are separate from the book form, so the books-mbx merge rules
  for book fields are unaffected. Editing a story someone just deleted gives Not Found.
- **Very large collections** (50 stories): listed in full; see SC-002.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The catalog MUST hold stories, each with a title, at least one author, a
  series and a number in that series (0–999.99, as for books).
- **FR-002**: A story MUST be contained in at least one catalog book; it MAY be in several.
  A story in no book MUST NOT exist.
- **FR-003**: Within a series, no two stories MAY share a number. A story MAY share a
  number with a book.
- **FR-004**: Any signed-in member MUST be able to add a new story to a book, add an
  existing story to a book, edit a story, and remove a story from a book; removing it from
  its last book deletes it after a confirmation that says so.
- **FR-005**: Adding a story MUST look up existing stories first (by series and number, and
  by title suggestions) and never silently create a duplicate (Principle II).
- **FR-006**: New author and series names typed for a story MUST go through the spec 005
  new-name prompt.
- **FR-007**: Edit book MUST list the book's stories and offer adding, editing and removing
  them; the entry page MUST list them read-only with a link to edit.
- **FR-008**: The series page MUST list stories in that series at their numbers among the
  books, with their containing books and the viewer's derived status (AC-11), include them
  in gap working (AC-12), report story progress (AC-13), and show which numbers a collection
  contains (AC-14).
- **FR-009**: A story's status MUST be derived from the viewer's own entries only and MUST
  NOT be stored.
- **FR-010**: An author linked to any story MUST count as having works for spec 008
  (not deletable, not listed as unused).
- **FR-011**: The title type-ahead on Add a book MUST also match story titles and suggest
  the containing books.
- **FR-012**: The JSON API MUST let clients read a story, list a book's or a series'
  stories, add a new or existing story to a book, edit a story, and remove a story from a
  book; all of it in the OpenAPI contract.
- **FR-013**: Every new page and control MUST work without JavaScript, be CSRF-protected
  where it changes data, and meet WCAG 2.2 AA and the spec 003 layouts.

### Key Entities

- **Story** (catalog): title, authors (ordered), series, number. Unique by series and
  number.
- **Story in book** (catalog): links a story to a book that contains it.
- **Book**, **Author**, **Series**: unchanged, except that a book now lists its stories.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Story title, authors, series, number | Catalog | All members | Any member |
| Which books contain a story | Catalog | All members | Any member |
| A story's status on the series page | Derived from personal | Owner only | Not stored |
| "K of L stories" | Derived from personal | Owner only | Not stored |

- **Duplication check**: a story collected in two books is one story, linked twice. Nothing
  catalog is copied into reading entries, and no per-story personal data is stored.
- **Cross-user access**: none. Story statuses read the viewer's own entries through the
  existing per-member data access (Principle I).

## AI Involvement *(mandatory)*

- **Generated content**: None.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: None.
- **Sent to external services**: None.

## API Changes *(include if feature changes the JSON API)*

- **New endpoints**: reading a story, listing a series' stories, adding a new or existing
  story to a book, editing a story, removing a story from a book (exact paths in the plan's
  contract).
- **Changed responses**: None. Book search may now also return a book because one of its
  stories matched.
- **Breaking changes**: None.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A member can record a collection's three stories in under two minutes from its
  Edit book page.
- **SC-002**: The series page stays within the existing budget (under 1 s at p95) for a
  series of 100 books and 100 stories in a 5,000-book catalog with 5,000 entries for the
  viewer; Edit book with 50 stories likewise.
- **SC-003**: No test or page view shows another member's reading data through a story.
- **SC-004**: No series ever holds two stories at the same number.

## Assumptions

- **Stories always have a series and number.** The aim is placing stories in a series
  timeline; a collection of unrelated stories is recorded as a plain book, as today.
- **No per-story reading status.** Finishing a collection marks all its stories finished
  for that member; tracking individual stories read (say, in a magazine) is a possible
  follow-up, not this spec.
- **Authors default to the book's** but are stored per story, since anthologies mix authors.
- **Stories are managed from Edit book**, not from Add a book: a member adds the collection
  first, then its stories.
  *Update (spec 013):* a new book's stories can now also be entered on Add a book; existing
  books' stories are still managed from Edit book.
- **Open Library import is unchanged**: it doesn't read story contents.
- **Release dates (spec 007)** don't apply to stories.
- **No table of contents order:** a book's stories are listed by series and number, not in
  the order printed in the book.
