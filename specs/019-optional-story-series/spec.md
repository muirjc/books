# Feature Specification: Stories Without a Series

**Feature Branch**: `019-optional-story-series`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "There is a current assumption that all anthologies are tied to
a series. This is not always true. A book of short stories by different authors may be
nothing more than a book of short stories. The series and number fields should be optional
on an anthology." (bead books-g2r)

Today every story in a collection or anthology must have a series and a number (specs 009
and 013). A book of short stories by different authors, with no series, can't be recorded:
the member has to invent a series for it.

## Clarifications

### Session 2026-11-26

- Q: Once a series is optional, what does a blank series on an Add a book story row mean when
  the book has a series? → A: It depends on the number. A row with a number and a blank
  series takes the book's series, as today. A row with no number and no series is a story
  without a series.
- Q: Where do stories without a series go in a book's story list, and in what order? → A:
  After the stories with a series (which keep their series-then-number order), in the order
  they were added to that book.
- Q: Should a story be allowed a series with no number (say an unnumbered Discworld short
  story)? → A: No. A story has a series and a number, or neither. For an unnumbered story in
  a series, leave the series off.
- Q: Should Edit book let a member move a story without a series up or down? → A: Not in
  this feature. To fix the order, remove the story and add it again, which puts it last.

## Overview

After this feature:
- **A story's series and number are optional.** A story may have both, or neither. It can't
  have a number without a series, or a series without a number.
- **Stories with a series** work as today: the same number rules, one story per series and
  number, shown at their place on the series page.
- **Stories without a series** show just their title and authors in their books, and appear
  on no series page.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record a book of unrelated stories (Priority: P1)

A member adds *The Best Short Stories of the Year*, an anthology of stories by different
authors with no series. On Add a book they tick **This book is an anthology or
collection**, type each story's title and author, leave series and number empty, and save.

**Why this priority**: it's the bead: such books can't be recorded today.

**Independent Test**: add an anthology with three stories and no series or numbers, then
check the book page lists the three stories with their authors and no numbers.

**Acceptance Criteria**:

- **AC-01**: **Given** Add a book with the anthology section, **When** a story row has a
  title, no number and no series, **Then** it saves as a story without a series, in this
  book, whether or not the book has a series. The section's hint says so: "Leave the number
  and series blank for a story that isn't part of a series."
- **AC-02**: **Given** a story row with a number and a blank series, **When** the book has a
  series, **Then** the story takes the book's series, as today (spec 013 AC-03).
- **AC-03**: **Given** a story row with a series typed and no number, **When** the member
  saves, **Then** nothing is saved, and the row says "Story N: Enter a number, or clear the
  series for a story that isn't part of a series". Everything typed is kept.
- **AC-04**: **Given** Add a story on Edit book (spec 009), whose series starts filled with
  the book's series, **When** the member clears the series and leaves the number empty,
  **Then** the story is added to this book without a series. A series with no number, or a
  number with no series, is refused with a message beside the field, and what was typed is
  kept.
- **AC-05**: **Given** Edit story, **When** the member clears a story's series and number,
  **Then** it becomes a story without a series in every book it's in. **When** they give a
  story without a series a series and number, **Then** the spec 009 rules apply, including
  the refusal when another story holds that series and number.
- **AC-06**: **Given** two stories without a series with the same title, **Then** both may
  exist: a title alone doesn't identify a story. To put an existing story without a series
  into another book, the member chooses it from the title suggestions on Add a story (spec
  009 AC-17).
- **AC-07**: **Given** a story row with a number and a blank series, **When** the book has
  no series, **Then** nothing is saved, and the row says "Story N: Choose a series for this
  story, or clear the number for a story that isn't part of a series" (spec 013 AC-11,
  reworded).

---

### User Story 2 - See stories without a series in their books (Priority: P1)

A member opens the anthology's book page, their entry, or an author's page, and sees each
story by title and author.

**Why this priority**: a saved story the member can't see is no use.

**Independent Test**: with an anthology holding two stories without a series and one with a
series, check the book page, entry page, Edit book, the author page and Edit author.

**Acceptance Criteria**:

- **AC-08**: **Given** a story without a series, **When** it's listed where "#n Series —
  Title" shows today (the book page, the entry page, Edit book, the author page's Stories
  list and Edit author), **Then** it shows its title and authors only, with no number,
  series or empty link. Stories with a series show as today.
- **AC-09**: **Given** a book with stories with and without a series, **When** its stories
  are listed, **Then** the stories with a series come first, by series name and then number
  (as today), followed by the stories without a series in the order they were added to this
  book. A story added to a second book goes last among that book's stories without a series.
- **AC-10**: **Given** a story without a series in two books, **Then** "Also in “X”" (spec
  016) shows on each book page as for any story.

---

### User Story 3 - Series pages stay about series (Priority: P2)

**Acceptance Criteria**:

- **AC-11**: **Given** a series page, a series' progress counts, the Series view's book
  counts (spec 018) and the series' Add #next row, **Then** they count and list only
  stories that have that series. A story without a series is on no series page.
- **AC-12**: **Given** a story that loses its series (AC-05), **When** that series page is
  next opened, **Then** the story is no longer on it.

---

### User Story 4 - The JSON API, privacy, access and speed (Priority: P2)

**Acceptance Criteria**:

- **AC-13**: **Given** the JSON API, **When** a client creates, edits, lists or reads stories
  (spec 009) or creates an entry with `stories` (spec 013), **Then** the series and number
  are optional, as on the forms (AC-03, AC-04), and responses give them as null for a story without
  a series. The published contract says so.
- **AC-14**: **Given** the existing stories, **When** the change is applied, **Then** every
  story keeps its series and number, and the change can be undone while every story still
  has a series.
- **AC-15**: **Given** the story rows, Edit story, and the pages in AC-08 showing stories
  without a series, **When** they're checked at the spec 003 widths, **Then** there's no
  sideways scroll, every control is at least 44 × 44 CSS px, axe reports no WCAG 2.2 AA
  violations, and everything works with JavaScript off.
- **AC-16**: **Given** 5,000 books, **When** a book page, entry page or series page with
  stories shows, **Then** it stays within the 1 s budget (p95).

### Edge Cases

- **A story without a series whose only book is removed:** it's deleted from the catalog
  after the spec 009 confirmation, as any story.
- **A number of 0:** a number of 0 with a series is still allowed (0–999.99); "no number" is
  an empty field, not 0.
- **The series is deleted:** spec 009 doesn't allow deleting a series that holds stories, and
  that doesn't change.
- **Status on stories:** a story without a series has no status of its own, as today; the
  member's status is the book's.
- **A series story with no place in the reading order** (say an unnumbered Discworld short
  story): it's recorded without a series (Clarifications). A series and no number is
  refused (AC-03, AC-04).
- **Undoing the change** (AC-14): it's refused while any story has no series, so no story is
  silently given a made-up series.

### Amended specs

This feature changes rules of earlier specs. Their criteria get dated notes:
- spec 009: AC-01 (the order of a book's stories), AC-02 (the number may be left blank,
  with the series cleared), AC-04 (no series is allowed, with no number);
- spec 013: AC-02 (the hint), AC-10 (a missing number is allowed when the series is blank
  too), AC-11 (reworded, and only for a row with a number).

Tests of what those criteria still require keep their tags; tests of the changed behaviour
are tagged `019/AC-xx`.

### Out of scope

- **Reordering** a book's stories (Clarifications). Removing a story and adding it again
  puts it last; a story only in this book is deleted on removal (spec 009 AC-19), so it's
  added again as a new story.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A story's series and number MUST be optional, and given together or not at
  all (AC-01–AC-07).
- **FR-002**: Stories with a series MUST keep every spec 009 and 013 rule, including one story
  per series and number.
- **FR-003**: Stories without a series MUST show by title and authors wherever stories are
  listed, in a defined order (AC-08–AC-10).
- **FR-004**: Series pages and counts MUST include only stories in that series (AC-11,
  AC-12).
- **FR-005**: The JSON API MUST accept and return stories without a series (AC-13).
- **FR-006**: The change MUST keep existing data and be reversible (AC-14), and meet the
  accessibility, layout and speed budgets (AC-15, AC-16).

### Key Entities

- **Story** (catalog): title, authors, the books it's in, and now an *optional* series and
  number, both or neither.
- **A story in a book**: now also remembers the order it was added to that book, used to
  list stories without a series (AC-09).

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Stories, their series and numbers | Catalog | All members | Any member |
| My status on a story's book | Personal | Owner only | Owner only |

- **Duplication check**: none. A story is still stored once, however many books it's in.
- **Cross-user access**: none new. Statuses come only from the viewer's own entries.

## AI Involvement *(mandatory)*

- **Generated content**: none.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: none.
- **Sent to external services**: none.

## API Changes

- **Changed schemas**: the story create, update and read schemas, and the `stories` items on
  entry create (spec 013), make `series_id` and `series_number` optional and nullable, both
  or neither.
- **Breaking changes**: for clients that read stories, `series_id`, `series_number` and the
  series name may now be null. No request that worked before is refused.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A member can record an anthology of unrelated stories, with no series, in one
  Add a book save.
- **SC-002**: No page shows an empty number, an empty series name or a broken series link
  for a story without a series.
- **SC-003**: Every existing story keeps its series and number after the change.
- **SC-004**: Pages that list stories stay within 1 s (p95) at 5,000 books.

## Assumptions

- **A title doesn't identify a story without a series** (AC-06). Reusing one in another book
  is done by choosing it from the title suggestions.
- **No new fields**: an anthology isn't a new kind of book; "anthology" is still just a book
  with stories.
- **The story's authors** default as today (spec 013: blank authors take the book's
  authors).
- **Status**: stories still have no status of their own (spec 009).
