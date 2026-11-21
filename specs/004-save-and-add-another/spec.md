# Feature Specification: Save and Add Another

**Feature Branch**: `004-save-and-add-another`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "Save and add another (bead books-g38): on Add a book, offer a way to save the book and go straight to a fresh Add a book form for the next one, without going through My books. Today every successful save redirects to My books, so entering several books (for example a run of books in one series) means clicking Add a book again each time. Keep plain Save as today. Decide which fields carry over to the next form (author, series with the next number, status, finished date) and which clear (title, ISBN, summary, notes); confirm which book was just added; put focus on Title; work without JavaScript; keep validation and conflict handling unchanged; meet WCAG 2.2 AA and the spec 003 phone, tablet and laptop layouts."

## Overview

Family members often add books in runs: several books by one author, or the next few books
in a series they are catching up on. Today Add a book has one button, **Add to my list**,
and every successful add goes to My books, so each further book means clicking **Add a
book** again and retyping the author and series.

This feature adds a second button, **Add and add another**. It saves the book exactly as
**Add to my list** does, then opens a fresh Add a book form with a confirmation naming the
book just added. The author, series, next number in the series and status are filled in
from the book just added, so the next book in a run usually needs only its title.

Nothing else about adding a book changes: the same fields, checks, error messages and
conflict choices apply to both buttons.

### What carries over

| Field | On the next form | Why |
|---|---|---|
| Authors | Same authors as the book just added | Runs are usually by one author |
| Series | Same series | Runs are often one series |
| Number in series | The next whole number (5 → 6, 4.5 → 5); blank if the book had no number | The next book in a run |
| Status | Same status | A run is usually all finished or all want to read |
| Date finished | Cleared | Each book is finished on a different day; a carried date would be silently wrong |
| Title, ISBN, summary, private notes | Cleared | Belong to one book only |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add a book and go straight to the next one (Priority: P1)

A member fills in Add a book and chooses **Add and add another**. The book is added to
their list, and they stay on Add a book with a confirmation ("Added “Death Masks” to your
list"), a link to the book just added, and an empty Title ready for typing.

**Why this priority**: this is the whole request: entering several books without going
through My books each time.

**Independent Test**: Sign in, fill in Add a book, choose **Add and add another**, and
check that the book is on the list, the page is a fresh Add a book form with the
confirmation, and Title has focus.

**Acceptance Criteria**:

- **AC-01**: **Given** a filled-in Add a book form, **When** the member chooses **Add and
  add another**, **Then** the book is added to their list exactly as **Add to my list**
  would add it, and they are shown Add a book again, not My books.
- **AC-02**: **Given** a book was just added with **Add and add another**, **When** the new
  form appears, **Then** it shows a confirmation naming the book ("Added “Death Masks” to
  your list") with a link to that book's page, and assistive technology announces it.
- **AC-03**: **Given** the new form after **Add and add another**, **When** it appears,
  **Then** keyboard focus is in Title, with or without JavaScript.
- **AC-04**: **Given** a filled-in form, **When** the member chooses **Add to my list** (or
  presses Enter in a field), **Then** the book is added and they go to My books with the
  usual "added" message, exactly as today.
- **AC-05**: **Given** the new form after **Add and add another**, **When** the member
  reloads the page or goes back and forward, **Then** the book is not added a second time.
- **AC-06**: **Given** JavaScript is off, **When** the member uses **Add and add another**,
  **Then** it behaves the same as with JavaScript on.

---

### User Story 2 - The next form is filled in for the next book in a run (Priority: P1)

After **Add and add another**, the new form already has the author, series and status of
the book just added, and the next number in the series, so adding the next book in a series
usually needs only its title.

**Why this priority**: without it the second button saves one click but still means
retyping the author and series for every book, which is most of the effort.

**Independent Test**: Add "Grave Peril", Dresden Files #3, Jim Butcher, Finished, with
**Add and add another**, then check the new form has Jim Butcher, The Dresden Files, 4 and
Finished filled in, and empty title, ISBN, date finished, summary and notes.

**Acceptance Criteria**:

- **AC-07**: **Given** a book added with **Add and add another**, **When** the new form
  appears, **Then** its authors are the same catalog authors as the book just added (all of
  them, in the same order), already chosen, so saving does not create new authors.
- **AC-08**: **Given** the book just added is in a series, **When** the new form appears,
  **Then** the series is the same catalog series, already chosen.
- **AC-09**: **Given** the book just added has a number in its series, **When** the new
  form appears, **Then** the number is the next whole number after it (3 → 4, 4.5 → 5).
  **Given** it has no number, or no series, **Then** the number is blank.
- **AC-10**: **Given** the new form, **When** it appears, **Then** status is the status the
  book was added with, and title, ISBN, date finished, summary and private notes are empty.
- **AC-11**: **Given** the new form, **When** the member changes or clears any carried-over
  field before saving, **Then** the book is saved with what they entered (carried-over
  values are only a starting point).
- **AC-12**: **Given** the member chose an existing catalog book from the title type-ahead
  and used **Add and add another**, **When** the new form appears, **Then** the carried-over
  values come from that catalog book (its authors, series and next number) and the status
  it was added with.
- **AC-13**: **Given** the suggested next number is already held by another book in the
  series, **When** the member saves without changing it, **Then** they see the usual "number
  taken" conflict, with its link to the book holding it (books-cay), and nothing is saved.

---

### User Story 3 - Errors and conflicts work the same with either button (Priority: P2)

If the form has a mistake or a conflict (missing title, author or series already in the
catalog, ISBN already in the catalog, book already on the list, number taken), the member
sees the same messages and choices as today, whichever button they used. When they fix it
and save, the button they chose still decides where they go next.

**Why this priority**: it keeps the new button from becoming a second, different way to add
a book with its own rules.

**Independent Test**: Submit an invalid form and each conflict with **Add and add
another**, check the page and messages match **Add to my list**, then fix and save and
check the member lands on a fresh Add a book form.

**Acceptance Criteria**:

- **AC-14**: **Given** a form with a validation error or a conflict, **When** the member
  chooses **Add and add another**, **Then** nothing is saved and the page shows the same
  messages, field values and choices as **Add to my list** would.
- **AC-15**: **Given** an error or conflict page reached with **Add and add another**,
  **When** the member chooses one of the conflict's own actions (use the existing author or
  series, or add the existing ISBN book instead), **Then** a successful save still leads to
  a fresh Add a book form, because they chose **Add and add another**. **When** they instead
  save with **Add to my list** or **Add and add another**, **Then** that button decides.
  The same holds the other way round for a page reached with **Add to my list**.
- **AC-16**: **Given** a book already on the member's list, **When** they add it again with
  **Add and add another**, **Then** they see the usual "Already on your list" choices (Read
  again, Open it), unchanged.

---

### User Story 4 - Fits every screen and stays accessible (Priority: P2)

Both buttons fit and are easy to use on an iPhone, an iPad and a laptop, and the page meets
the same accessibility standard as the rest of the app.

**Why this priority**: the family adds books on all three devices; spec 003 set the layout
rules this page must keep.

**Independent Test**: Open Add a book at phone, tablet and laptop widths and with 200% text
size; check the buttons, the confirmation and the automated accessibility checks.

**Acceptance Criteria**:

- **AC-17**: **Given** phone, tablet and laptop widths (360, 390, 820, 1,024 and 1,440 px),
  **When** Add a book loads, **Then** both buttons are fully visible without sideways
  scrolling, each target is at least 44 × 44 px, and **Add to my list** comes first in
  reading and Tab order.
- **AC-18**: **Given** the new form with its confirmation, **When** automated WCAG 2.2 AA
  checks run at phone, tablet and laptop widths, **Then** there are no violations, and the
  spec 003 layout checks for Add a book (form columns, paired fields, focus order) still
  pass.

### Edge Cases

- **Another member's entry**: the confirmation and carry-over come only from the signed-in
  member's own just-added entry. If the next form is asked to carry over from an entry that
  isn't theirs, or no longer exists (removed in another tab), it opens as a plain empty
  Add a book form, revealing nothing about that entry (Principle I).
- **Carried author or series changed meanwhile**: if another member renames the carried
  author or series between the two adds, the next form shows the current name; if it was
  deleted (for example an author with no books, books-4oc), that field is left empty.
- **Very long series numbers or titles**: the confirmation and fields keep the spec 003
  rules (no sideways scroll; long text wraps).
- **Book from Open Library import**: import has its own page and confirm flow (spec 002) and
  is unchanged.
- **Enter key**: pressing Enter in a field submits with **Add to my list**, as today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Add a book MUST offer two ways to save: **Add to my list** (unchanged) and
  **Add and add another**.
- **FR-002**: Both ways MUST save the book and the member's reading entry with the same
  rules, checks and messages; only what happens after a successful save differs.
- **FR-003**: After a successful **Add and add another**, the member MUST be shown a fresh
  Add a book form, not My books.
- **FR-004**: The fresh form MUST show a confirmation naming the book just added, with a
  link to its page, announced to assistive technology.
- **FR-005**: The fresh form MUST place keyboard focus in Title without needing
  JavaScript.
- **FR-006**: The fresh form MUST carry over the authors (all, in order, as catalog
  authors), series (as the catalog series) and status of the book just added, and suggest
  the next whole number in the series; all other fields MUST be empty.
- **FR-007**: Carried-over values MUST be ordinary editable form values; nothing is saved
  until the member submits the next form.
- **FR-008**: Reloading or revisiting the fresh form MUST NOT add a book again.
- **FR-009**: Carry-over and confirmation MUST come only from the signed-in member's own
  entry; any other request MUST give a plain empty form and reveal nothing.
- **FR-010**: Pressing Enter in a field MUST submit as **Add to my list**.
- **FR-011**: The feature MUST work without JavaScript.
- **FR-012**: The page MUST meet WCAG 2.2 AA and the spec 003 layout rules at phone, tablet
  and laptop widths and at 200% text size.

### Key Entities

- **Reading entry** (existing, personal): the entry just added; its book, status and owner
  decide the confirmation and carry-over.
- **Book, authors, series** (existing, catalog): read to fill the next form. No new data is
  stored.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Book, authors, series of the book just added (carried over) | Catalog | All members | Any member (unchanged) |
| Status of the entry just added (carried over) | Personal | Owner only | Owner only (unchanged) |
| The new book and entry saved with either button | Catalog / Personal | As today | As today |

- **Duplication check**: no catalog data is copied into personal records; carry-over only
  pre-fills a form.
- **Cross-user access**: carry-over reads only the signed-in member's own entry; another
  member's entry gives a plain empty form (FR-009), with a cross-user test.

## AI Involvement *(mandatory)*

- **Generated content**: None. The optional summary field works as today and is cleared on
  the next form.
- **Approval step**: N/A.
- **Provenance stored**: N/A.
- **Fallback on failure**: N/A.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: None.
- **Sent to external services**: None.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After the first book, a member can add the next book in a numbered series by
  typing only its title and choosing **Add and add another**: no other field to fill in and
  no visit to My books.
- **SC-002**: Adding five books in a row takes five saves and no other page visits, compared
  with five saves plus four trips through My books and Add a book today.
- **SC-003**: Every acceptance criterion has an automated test, including runs without
  JavaScript and at phone, tablet and laptop widths.
- **SC-004**: Add a book still loads within the existing page budget (spec 001), with or
  without carry-over.

## Assumptions

- The second button's label is **Add and add another**, next to **Add to my list**; the
  wording can change without changing this spec.
- Date finished is cleared rather than carried over (see "What carries over"); members
  catching up on a series usually add dates per book or leave them blank.
- The next number is the next whole number; series with half-numbered novellas (4.5) still
  suggest the next whole book, and the member can change it.
- Import from Open Library (spec 002) already covers adding many books by one author at
  once and is unchanged.
- No change to the JSON API: this is a page flow only.
