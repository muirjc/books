# Feature Specification: Anthology Stories on Add a Book

**Feature Branch**: `013-anthology-on-add`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "Add an anthology's stories while adding the book (bead
books-1a5). On Add a book (every entry point), a checkbox 'This book is an anthology or
collection' reveals story rows (title, authors, series, number); 'Add another story' adds a
row; a row can be removed. Spec 009 rules hold. Saving is atomic. Works without JavaScript.
The JSON API's create-entry-with-new-book request gains an optional stories list."
Decisions made with the user on 2026-11-23: every story still needs a series and number
(stories outside a series are a separate bead); a checkbox with story rows; the JSON API
gets the stories list too; every Add a book entry point offers it.

## Overview

Today a collection's stories (spec 009) can only be recorded after the book exists, from
Edit book, through a link that is easy to miss. A member adding *Side Jobs* has to add the
book, find Edit book, then add each story one by one.

This feature lets the member record the stories on **Add a book** itself:

- A checkbox, **This book is an anthology or collection**, opens a **Stories in this book**
  section with one story row.
- Each row has a title, a number, and optionally a series and an author. A blank series or
  author means "the same as the book's".
- **Add another story** adds a row and **Remove** takes one away.
- One save adds the book, the member's reading entry and every story, or nothing at all.

All the spec 009 rules still hold. Every story has a series and a number. No series holds
two stories at one number. An existing story is offered, never duplicated.

### Example

A member adds *Side Jobs* by Jim Butcher, series The Dresden Files, no number, and ticks the
checkbox. They fill in three rows, leaving series and authors blank:

| # | Title | Number | Series (blank = the book's) | Author (blank = the book's) |
|---|---|---|---|---|
| 1 | Restoration of Faith | 1.5 | | |
| 2 | Publicity and Advertising | 2.5 | | |
| 3 | Something Borrowed | 6.5 | | |

They choose **Add to my list**. *Side Jobs* is on their list, Edit book lists the three
stories, and the Dresden Files page shows them at #1.5, #2.5 and #6.5.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record a collection's stories while adding it (Priority: P1)

A member adding an anthology ticks the checkbox and types its stories into rows on the same
form. They add the whole thing in one save.

**Why this priority**: this is the whole feature; everything else supports it.

**Independent Test**:
1. Add *Side Jobs* with three story rows, as in the Example.
2. Check that the book, the entry and three stories are saved.
3. Check that the stories use the book's series and authors.
4. Check that Edit book and the series page list them.

**Acceptance Criteria**:

- **AC-01**: **Given** Add a book with no catalog book chosen, **When** the form opens,
  **Then** it shows an unticked checkbox, **This book is an anthology or collection**, below
  the book's fields.
- **AC-02**: **Given** the checkbox is ticked, **When** the section shows, **Then**:
  - it is headed **Stories in this book** and has one empty story row;
  - each row has a title, a number, a series and an author;
  - a hint says a blank series uses the book's series, and a blank author uses all the
    book's authors. A story with several authors of its own gets the others on Edit book.
- **AC-03**: **Given** the book's details and valid story rows, **When** the member chooses
  **Add to my list** or **Add and add another** (spec 004), **Then**:
  - the book, their entry and each story are saved together;
  - every story is in this book;
  - a blank series takes the book's series and blank authors take the book's authors;
  - the confirmation names the book and says how many stories were added.
- **AC-04**: **Given** the section is showing, **When** the member chooses **Add another
  story**, **Then** the form comes back with everything typed kept, plus one more empty row,
  and focus is on that row's title. Nothing is saved.
- **AC-05**: **Given** two or more rows, **When** the member chooses **Remove** on one,
  **Then** the form comes back without that row and with everything else kept. Focus is on
  the **Stories in this book** heading. Nothing is saved. The last remaining row has no
  **Remove**.
- **AC-06**: **Given** 50 story rows, **When** the form shows, **Then** **Add another
  story** is not offered, and a note says 50 is the most for one save.
- **AC-07**: **Given** a row that is completely empty, **When** the member saves, **Then**
  that row is ignored, not treated as an error. **Given** every row is empty, **When** the
  member saves, **Then** the book is added with no stories.
- **AC-08**: **Given** the checkbox is unticked, **When** the member saves and some row has
  text in it (possible when JavaScript is off), **Then** nothing is saved. A message beside
  the checkbox says to tick it to save the stories, or to clear them. Everything typed is
  kept.
- **AC-09**: **Given** Add a book started from a series gap (spec 006), **When** the member
  ticks the checkbox, **Then** the book's series is already filled with that series, so a
  blank story series also means that series.

---

### User Story 2 - Mistakes are caught before anything is saved (Priority: P1)

The spec 009 story rules and the spec 005 new-name check apply to every row. One bad row
stops the whole save, and the member sees what to fix without losing anything typed.

**Why this priority**: without it, an anthology save could half-succeed or duplicate stories.

**Independent Test**:
1. Save with one good row and one row missing its number. Check that nothing is saved and
   the message sits beside that row's number.
2. Fix the number and save again. Check that the book and both stories are saved.

**Acceptance Criteria**:

- **AC-10**: **Given** a row with text, **When** its title is blank, its number is missing,
  or its number is outside 0–999.99, **Then**:
  - nothing is saved: not the book, the entry or any story;
  - each problem is shown beside its field and listed in the error summary, naming the row
    ("Story 2: Enter a number");
  - everything typed is kept.
- **AC-11**: **Given** a row whose series is blank and a book with no series, **When** the
  member saves, **Then** the row is refused with "Story N: Choose a series for this story,
  or give the book a series".
- **AC-12**: **Given** two rows with the same series and number, **When** the member saves,
  **Then** both rows are marked ("Story 1 and Story 3 have the same number in The Dresden
  Files") and nothing is saved.
- **AC-13**: **Given** a row whose series and number already belong to a catalog story (say
  #2.5 *Publicity and Advertising*, in *Side Jobs*), **When** the member saves, **Then**:
  - nothing is saved;
  - the row names the existing story and the book(s) it's in;
  - the row offers **Use that story** or changing the number.

  If the member chooses **Use that story**, the row becomes that existing story, shown
  read-only with **Remove**. The next save adds that story to the new book (spec 009
  AC-17) instead of creating a second one.
- **AC-14**: **Given** a row whose series and number belong to a **book** (not a story),
  **When** the member saves, **Then** it is allowed (spec 009 AC-06). The new anthology may
  share a number with one of its own stories in the same way.
- **AC-15**: **Given** new author or series names typed on story rows, **When** the member
  saves, **Then**:
  - the spec 005 new-name prompt appears beside each such field, together with any new
    names on the book;
  - a name typed in several places (on the book and on two rows, say) is confirmed once
    and the confirmation applies everywhere it is typed;
  - nothing is saved until the prompts are answered.
- **AC-16**: **Given** another member saves a story at the same series and number while this
  member's form is open, **When** this member saves, **Then** nothing is saved and the
  affected row shows the AC-13 choice.
- **AC-17**: **Given** the save fails for any reason after the book or a story was created,
  **When** the error is shown, **Then** nothing from this save remains in the catalog or the
  member's list.

---

### User Story 3 - Fits the rest of Add a book (Priority: P2)

The story section behaves sensibly alongside the existing Add a book features: choosing a
catalog book, duplicate-book conflicts, AI summary drafts and Add and add another.

**Why this priority**: it stops the new section from surprising members in flows they
already use.

**Independent Test**:
1. With story rows filled in, use **Draft summary with AI**. Check the rows are kept.
2. Trigger a duplicate-book conflict and choose the existing book. Check the message says
   the stories were not added.

**Acceptance Criteria**:

- **AC-18**: **Given** Add a book with a catalog book already chosen (spec 006, or a title
  suggestion), **When** the form shows, **Then**:
  - there is no anthology checkbox or story section;
  - a short note says a book's stories can be added from its Edit book page, linked once
    the book is on the member's list.
- **AC-19**: **Given** story rows filled in, **When** the member uses **Draft summary with
  AI** or **Regenerate** (spec 012), or the page comes back for any other reason (an error,
  a new-name prompt), **Then** the checkbox state and every row are kept exactly.
- **AC-20**: **Given** story rows filled in and a book that matches an existing catalog book
  (the duplicate-book conflict), **When** the member chooses to add the existing book
  instead, **Then**:
  - the existing book is added to their list;
  - none of the typed stories are saved;
  - the confirmation says so and links to that book's Edit book to add stories there.
- **AC-21**: **Given** **Add and add another** saved an anthology, **When** the fresh form
  shows, **Then** the checkbox is unticked and there are no story rows. The usual spec 004
  fields carry over.

---

### User Story 4 - JSON API clients can do the same (Priority: P2)

A client creating an entry with a new book can include the book's stories in the same
request.

**Why this priority**: it keeps the API in step with the web form (Principle VI).

**Independent Test**:
1. POST an entry with a new book and three stories. Check the response matches the
   contract.
2. Read the book's stories. Check all three are there.

**Acceptance Criteria**:

- **AC-22**: **Given** a create-entry request with a new book and a `stories` list, **When**
  the client sends it, **Then**:
  - each item is either a new story (title, number, and optionally a series and authors,
    defaulting to the book's) or an existing story by id;
  - the book, the entry and the stories are saved together;
  - the response matches the published contract.
- **AC-23**: **Given** a `stories` list, **When** it has more than 50 items, an item has a
  missing title or number, or an item has no series and the book has none either, **Then**
  the request is refused with a validation error naming the item, and nothing is saved.
- **AC-24**: **Given** a `stories` list, **When** two items share a series and number,
  **Then** the request is refused with a validation error, and nothing is saved.
- **AC-25**: **Given** an item whose series and number already belong to a catalog story,
  **When** the client sends it, **Then** the request is refused with a conflict that
  identifies the existing story, and nothing is saved.
- **AC-26**: **Given** a create-entry request for an existing book (`book_id`), **When** it
  includes `stories`, **Then** it is refused with a validation error. Stories for an
  existing book use the spec 009 story endpoints.
- **AC-27**: **Given** a create-entry request with no `stories`, **When** the client sends
  it, **Then** it behaves exactly as today.

---

### User Story 5 - Usable everywhere (Priority: P2)

**Acceptance Criteria**:

- **AC-28**: **Given** Add a book with the story section open, rows with errors, the AC-13
  existing-story choice and the new-name prompts, **When** each is checked at phone, tablet
  and laptop widths (spec 003), **Then**:
  - there is no sideways scroll;
  - every control is at least 44 × 44 CSS px;
  - axe reports no WCAG 2.2 AA violations.
- **AC-29**: **Given** JavaScript is off, **When** a member ticks the checkbox, adds,
  removes and fills in rows, and saves, **Then** everything works as with JavaScript on.
  With JavaScript off the story section is always visible under the checkbox. With
  JavaScript on, ticking or unticking the checkbox shows or hides it without a page load.
- **AC-30**: **Given** a screen-reader or keyboard user, **When** they work through the
  story section, **Then**:
  - each row is a group named "Story N";
  - each **Remove** button says which story it removes ("Remove story 2");
  - every action can be done by keyboard alone, in reading order.

### Edge Cases

- **Unticking the box after typing rows (JavaScript on):** the rows are hidden, not erased.
  Saving with the box unticked and rows filled in is refused, as in AC-08, so typed stories
  are never silently thrown away.
- **A row with only authors or only a series filled in:** it counts as a row with text. Its
  missing title and number are reported (AC-10).
- **A story row whose series differs from the book's:** allowed (spec 009 edge case). It
  shows on its own series' page.
- **The same existing story chosen in two rows:** refused as two rows with the same series
  and number (AC-12).
- **A story's author typed identically to one of the book's new authors:** one new-name
  confirmation, one author created (AC-15).
- **Another member's data:** nothing personal is shown or written beyond the member's own
  new entry. Story rows only touch the shared catalog (Principle I).
- **Very large collections:** 50 rows in one save; more can be added afterwards from Edit
  book.
- **Stale or tampered form data** (a story id that no longer exists, a row index out of
  range, a Remove for a missing row): the form comes back with a message on the affected row
  and nothing is saved. It is never a server error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Add a book MUST offer a **This book is an anthology or collection** checkbox
  whenever the member is adding a new catalog book. It MUST NOT be offered when a catalog
  book is chosen.
- **FR-002**: When ticked, the form MUST let the member enter 1 to 50 story rows. Each row
  has a title, a number, an optional series and an optional author. A blank series means the
  book's series and a blank author means all the book's authors.
- **FR-003**: The member MUST be able to add and remove rows without saving and without
  losing anything typed, with or without JavaScript.
- **FR-004**: Saving MUST be all-or-nothing. The new book, the member's entry and every story
  are saved, or none of them are.
- **FR-005**: Every saved story MUST satisfy spec 009:
  - a title, at least one author, a series and a number in 0–999.99;
  - no other story at the same series and number;
  - contained in the new book.
- **FR-006**: A row that matches an existing story's series and number MUST be offered as
  that story (Principle II). A second story MUST NOT be created.
- **FR-007**: Two rows on one form MUST NOT share a series and number.
- **FR-008**: New author and series names typed on rows MUST go through the spec 005
  new-name prompt, together with the book's, with one confirmation per distinct name.
- **FR-009**: Errors MUST be shown beside the field and in the error summary, naming the row
  number, and MUST keep everything typed.
- **FR-010**: Saving with the checkbox unticked MUST NOT silently discard rows that have text.
- **FR-011**: The JSON API's create-entry request MUST accept an optional `stories` list
  alongside a new book, with the same rules and atomicity as the form. The list MUST be refused for an
  existing book. The contract MUST be updated, as a non-breaking addition.
- **FR-012**: Every new control MUST work without JavaScript, stay CSRF-protected, and meet
  WCAG 2.2 AA and the spec 003 layouts.
- **FR-013**: Adding a book with no stories MUST behave exactly as before, on the form and in
  the API.

### Key Entities

- **Story** and **Story in book** (spec 009): unchanged. This feature only creates them
  through a new path.
- **Story row** (form only, never stored): a story being typed on Add a book. It holds the
  title, number, series and author, or a chosen existing story.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Story title, authors, series, number | Catalog | All members | Any member |
| Which books contain a story | Catalog | All members | Any member |
| The member's reading entry for the new book | Personal | Owner only | Owner only |
| Story rows while being typed | Not stored | The member filling in the form | — |

- **Duplication check**: stories are stored once, in the catalog, and linked to the book.
  Nothing catalog is copied into the reading entry. An existing story is linked, not copied
  (AC-13, FR-006).
- **Cross-user access**: none. The only personal record written is the member's own new
  entry, as on Add a book today.

## AI Involvement *(mandatory)*

- **Generated content**: None new. The spec 012 summary draft on Add a book is unchanged.
  Story rows are never sent to the AI.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: None.
- **Sent to external services**: None.

## API Changes *(include if feature changes the JSON API)*

- **New endpoints**: None.
- **Changed requests**: the create-entry request gains an optional `stories` list, allowed
  only with a new book.
  Its items have the same shape as the spec 009 add-a-story request (a new story, or an
  existing one by id).
- **Breaking changes**: None. Omitting `stories` behaves as today.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A member can add a three-story collection, with its stories, in under two
  minutes from Add a book. That's one save instead of one save per story.
- **SC-002**: Saving Add a book with 50 story rows completes within the existing form budget
  (under 1 s at p95) in a 5,000-book catalog, and adding a row stays within it too.
- **SC-003**: No failed save leaves a partial book, entry or story behind (AC-17), across
  every failure case tested.
- **SC-004**: No series ever holds two stories at the same number after any Add a book save.
- **SC-005**: A member with JavaScript off can complete the Example in the same number of
  saves as with it on, plus one page load per extra row.

## Assumptions

- **Stories keep the spec 009 rule: series and number required.** An anthology of unrelated,
  unnumbered stories is still added as a plain book. Stories outside a series are a
  separate follow-up bead.
- **One author per row on the form.** Blank means all of the book's authors. Most
  anthology stories have one author. A co-written story gets its other authors on Edit book.
  The JSON API takes a full author list per story.
- **Blank means "the book's"** for a row's series and author. This avoids copying the
  book's fields into each row as they are typed, which would need JavaScript. Explicit
  values on a row always win.
- **No table-of-contents order:** as in spec 009, the stories are listed by series and
  number after saving, not in the order they were typed.
- **Editing stories afterwards** stays on Edit book (spec 009). Add a book only creates new
  stories or links existing ones.
- **Title type-ahead for story rows** (suggesting existing stories by title) is not
  included. An existing story is found by series and number (AC-13), as spec 009 AC-05 does.
- **Open Library import (spec 002)** is unchanged and never fills story rows.
