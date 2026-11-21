# Feature Specification: Confirm New Author and Series Names

**Feature Branch**: `005-confirm-new-names`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description (bead books-ca5): "values should not be saved until the save button is clicked. Otherwise typos get added into the data and there is no simple way to clean them up." Seen on Add a book and on a book's page / Edit book. Agreed scope: before Save creates a new author or series, ask the member to confirm it, offering close matches already in the catalog.

## Overview

Nothing is written before a member chooses Save. But on Save, every author or series name
the member typed, instead of picking it from the suggestions, quietly becomes a new record
in the shared family catalog. The only guard today is for an exact match ("Already in the
catalog: “Jim Butcher”"). A near miss, such as "J DM Robb" for "J.D. Robb", is added with
no question. When the book is corrected later, the misspelt record stays behind, and
authors and series can't be deleted (books-4oc).

This feature adds one confirmation step. When Save would create a new author or series,
nothing is saved yet. The page comes back with the member's input kept, and for each new
name it says it will be added to the family catalog, offers close matches already in the
catalog, and asks the member to confirm. A name is created only after the member confirms
that exact name.

It applies wherever a book's authors and series are typed: Add a book, a book's page (Book
details) and Edit book. Import from Open Library (spec 002) has its own author matching and
is unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A new name needs a yes before it is added (Priority: P1)

A member adds "Naked in Death" and types the author "J DM Robb" instead of picking "J.D.
Robb" from the suggestions. On Save, nothing is saved. The page says "“J DM Robb” is not in
the family catalog yet" and offers "Use “J.D. Robb”" and "Add “J DM Robb” as a new author".
The member picks J.D. Robb, and the book is saved with the existing author.

**Why this priority**: this stops typos at the source, which is the request.

**Independent Test**: Seed J.D. Robb. Save Add a book with author "J DM Robb": no author,
book or entry is created and the page offers J.D. Robb. Choose "Use “J.D. Robb”": the book
is saved with J.D. Robb and no new author exists.

**Acceptance Criteria**:

- **AC-01**: **Given** Add a book with an author name typed that is not in the catalog and
  was not picked from the suggestions, **When** the member saves, **Then** nothing is saved
  (no author, series, book or entry), and the page shows the form with everything they
  entered, plus a notice for that name: "“J DM Robb” is not in the family catalog yet."
- **AC-02**: **Given** that notice, **When** catalog authors have similar names, **Then** up
  to three are offered as "Use “J.D. Robb”" choices, closest first; choosing one saves the
  book with that existing author and creates no new author.
- **AC-03**: **Given** that notice, **When** the member chooses "Add “J DM Robb” as a new
  author", **Then** the book is saved and "J DM Robb" is added to the catalog.
- **AC-04**: **Given** a new series name typed (not picked), **When** the member saves,
  **Then** the same applies: nothing saved, "“Dresdin Files” is not in the family catalog
  yet.", similar series offered as "Use “The Dresden Files”", and "Add “Dresdin Files” as a
  new series".
- **AC-05**: **Given** several new names in one save (for example two new authors and a new
  series), **When** the member saves, **Then** each new name gets its own notice and
  choices on the same page, and the book is saved only once every new name is either
  confirmed or replaced by an existing one.
- **AC-06**: **Given** a member confirmed "J DM Robb" and then edits that name before saving
  again, **When** they save, **Then** the edited name needs its own confirmation (a
  confirmation covers only the exact name confirmed).
- **AC-07**: **Given** names picked from the suggestions, or typed exactly as an existing
  catalog name (any capitals), **When** the member saves, **Then** no new-name step appears.
  A picked name saves as today, and an exact typed match keeps today's "Already in the
  catalog" choice.

---

### User Story 2 - The same on a book's page and Edit book (Priority: P1)

A member corrects a book's author on its page (Book details) or on Edit book, and types the
new name. If that name is not in the catalog, they get the same confirmation before
anything changes.

**Why this priority**: the user saw typos arrive this way too; the book's page edits the
shared catalog book directly.

**Independent Test**: On a book's page, change the author to a new typed name and save:
the book and the reading entry are unchanged, and the page offers the confirmation. Confirm,
and the book is saved with the new author.

**Acceptance Criteria**:

- **AC-08**: **Given** a book's page (Book details and My reading saved together), **When**
  the member saves a new typed author or series name, **Then** neither the book nor their
  reading changes until the name is confirmed or replaced, and the confirmation works as in
  AC-01 to AC-06.
- **AC-09**: **Given** Edit book, **When** the member saves a new typed author or series
  name, **Then** the same confirmation applies.
- **AC-10**: **Given** a book's page or Edit book where the authors and series are
  unchanged, **When** the member saves other changes (title, notes, status), **Then** no
  confirmation appears.

---

### User Story 3 - Choices keep working with the rest of the form (Priority: P2)

The confirmation behaves like the other choices on these pages: it works without
JavaScript, keeps the member's input and the button they chose (spec 004), and shows any
other errors on the form at the same time.

**Why this priority**: keeps one consistent way to fix a form, and keeps "Add and add
another" runs smooth.

**Acceptance Criteria**:

- **AC-11**: **Given** a form with a new name and a field error (for example a missing
  title or a bad ISBN), **When** the member saves, **Then** the page shows the field errors
  as today and the new-name notice together, and nothing is saved. (A series number already
  taken can only be found when the book is written, so it shows on the save after the
  names are settled.)
- **AC-12**: **Given** Add a book reached with **Add and add another** (spec 004), **When** a
  new-name choice is made, **Then** a successful save still leads to the next-book form; on
  that form the new author, now in the catalog, is carried over already chosen and needs
  no confirmation.
- **AC-13**: **Given** JavaScript is off, **When** the member saves a new name and confirms
  it, **Then** it works the same as with JavaScript on.
- **AC-14**: **Given** the confirmation is showing, **When** a screen-reader user arrives on
  the page, **Then** the error summary at the top names each new name with a link to its
  field, each choice is a button with a clear label, targets are at least 44 × 44 px, and
  the page has no WCAG 2.2 AA violations at phone, tablet and laptop widths.

### Edge Cases

- **Name added by someone else meanwhile**: if another member adds the exact name between
  the notice and the confirmation, saving uses the existing record (today's "Already in the
  catalog" choice), not a duplicate.
- **Very similar names that are not the same author**: close matches are only offered; the
  member can always confirm their own name.
- **No similar names**: the notice and the "Add … as a new author" choice still appear,
  with no "Use" choices.
- **Pen names**: matching also looks at an author's real name, so typing a real name offers
  the pen name that has it.
- **Another member's data**: suggestions come only from the shared catalog (authors and
  series), which every member already sees; no personal data is shown.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Saving Add a book, a book's page (Book details) or Edit book MUST NOT create an
  author or series unless the member has confirmed that exact name on this form.
- **FR-002**: When a save would create an unconfirmed name, the system MUST save nothing and
  show the form again with the member's input, a notice per new name, and the choices.
- **FR-003**: The choices for each new name MUST be: use one of up to three similar catalog
  names (closest first), or add the typed name as new.
- **FR-004**: Similar names MUST be found among catalog authors (name and real name) or
  catalog series by a closeness measure that catches small typos, punctuation and spacing
  differences (for example "J DM Robb" ~ "J.D. Robb", "Dresdin Files" ~ "The Dresden
  Files").
- **FR-005**: A confirmation MUST apply only to the exact name confirmed; a changed name
  needs a new confirmation.
- **FR-006**: Names picked from the suggestions, names already chosen (carried over or the
  book's current ones), and exact matches MUST NOT trigger the new-name step.
- **FR-007**: The step MUST show together with any other errors on the form, and keep the
  spec 004 button choice.
- **FR-008**: The feature MUST work without JavaScript and meet WCAG 2.2 AA and the spec 003
  layouts.
- **FR-009**: Import from Open Library and the JSON API MUST be unchanged.

### Key Entities

- **Author, Series** (existing, catalog): read to find similar names; created only after
  confirmation. No new tables or columns.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Author and series names (for similar names) | Catalog | All members | Any member, after confirmation |
| Book, reading entry being saved | Catalog / Personal | As today | As today, only after every new name is settled |

- **Duplication check**: nothing is copied; the feature prevents duplicate-looking catalog
  records.
- **Cross-user access**: no personal data is read or shown; similar names come from the
  shared catalog.

## AI Involvement *(mandatory)*

- **Generated content**: None.
- **Approval step**: N/A.
- **Provenance stored**: N/A.
- **Fallback on failure**: N/A.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: None.
- **Sent to external services**: None.

## API Changes *(include if feature changes the JSON API)*

- **New endpoints**: None.
- **Breaking changes**: None. The JSON API keeps creating names from explicit fields; this
  step is for the pages, where typing is the risk.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No author or series is created from a page form without the member confirming
  its exact name (checked by tests on all three pages).
- **SC-002**: For the reported typo "J DM Robb" with "J.D. Robb" in the catalog, "J.D. Robb"
  is the first choice offered; likewise for a set of at least ten typical typos (extra or
  missing punctuation, one wrong letter, a missing "The"), the intended name is among the
  three offered.
- **SC-003**: Adding a book whose author and series are picked from the suggestions takes
  no more steps than today.
- **SC-004**: Every acceptance criterion has an automated test, including without
  JavaScript and at phone, tablet and laptop widths.

## Assumptions

- Exact case-insensitive matches keep today's "Already in the catalog" choice; this feature
  covers names that are not exact matches.
- The catalog is small (one family: hundreds to a few thousand authors and series), so
  comparing a typed name with every catalog name is acceptable.
- Removing typos already in the catalog, and tidying up names left with no books, are
  separate work (books-4oc).
- The JSON API is used by tools that send names deliberately and is unchanged.
