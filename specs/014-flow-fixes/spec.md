# Feature Specification: Flow Fixes

**Feature Branch**: `014-flow-fixes`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "Flow fixes from the UI flow review on 2026-11-23 (bead
books-gjh)." The fixes cover:
- back links;
- story entry points (an entry page always offers Add a story; Edit book jump link; Add
  and add another for stories);
- an Add #next row and an Add a collection link on series pages;
- Add a book by this author;
- a Catalog link after an import;
- navigation highlights and the shorter "Import" label;
- a Change password link;
- admin confirmations;
- the favorite-authors link near the Author filter;
- jump links on long pages.

Also fixes a dead end from spec 013 AC-20: "Add them from Edit book" with no way to get
there. Decision made with the user on 2026-11-23: the series page's story link opens Add a
book as a new collection, with the series filled in and the anthology box ticked.

## Overview

A review of every page on 2026-11-23 found places where a member gets stuck or has to go
the long way round:
- no way back from an edit page;
- no way to start adding stories to a book already on the list;
- no link to change your own password;
- admin actions that change an account with one click and no confirmation.

This feature makes small, separate fixes to those pages. It adds no new data and changes
no rules.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add stories to a book that is already on my list (Priority: P1)

A member has *Side Jobs* on their list and realises it's a collection. From its entry page
they can start adding its stories, one after another.

**Why this priority**: it is the dead end the user hit (spec 013 AC-20), and it's the
only way to turn an existing book into an anthology.

**Independent Test**:
1. Open the entry page of a book with no stories. Choose **Add a story**.
2. Add two stories with **Add and add another**.
3. Check that the entry page lists both.

**Acceptance Criteria**:

- **AC-01**: **Given** a member's entry for a book with no stories, **When** they open the
  entry page, **Then** a **Stories in this book** section says "No stories recorded. If
  this book is an anthology or collection, add its stories." and offers **Add a story**.
  With stories, it lists them as today, and offers both **Add a story** and **Edit the
  stories**.
- **AC-02**: **Given** spec 013 AC-20 (the existing book was added instead, and the typed
  stories were not), **When** the entry page opens, **Then** the notice says "The stories
  you typed were not added. Add them with Add a story below." and **Add a story** is on
  the page.
- **AC-03**: **Given** the Add a story form, **When** the member chooses **Add and add
  another**, **Then**:
  - the story is saved exactly as **Add story** would save it;
  - a fresh Add a story form for the same book opens, saying which story was added;
  - the series and authors start as the book's, and focus is on the title.

  Every error and conflict behaves as today (spec 009 AC-04 to AC-07). This works without
  JavaScript.
- **AC-04**: **Given** Add a story opened from an entry page, **When** the member saves or
  cancels, **Then** they return to that entry page. Opened from Edit book, they return to
  Edit book as today.
- **AC-05**: **Given** Edit book, **When** it opens, **Then**:
  - a "Jump to: Stories in this book" link near the top goes to that section;
  - the section's hint reads "For an anthology or collection: each story gets its place
    in its series."

---

### User Story 2 - Find my way back and around (Priority: P1)

Every page a member reaches from somewhere has a way back. The main navigation shows
which area they are in.

**Why this priority**: getting lost is the most common complaint from the review.

**Independent Test**: open each edit page and the Summary page. Check the back link goes
where expected and the navigation highlights the right tab.

**Acceptance Criteria**:

- **AC-06**: **Given** Edit book, **When** the member has an entry for the book, **Then**
  the page starts with "Back to “<title>”", linking to their entry. Otherwise it starts
  with "Back to the catalog".
- **AC-07**: **Given** the Summary page, **When** it opens, **Then** it starts with a back
  link: to the member's entry if they have one, otherwise to Edit book.
- **AC-08**: **Given** Edit series, **When** it opens, **Then** it links to the series page
  ("View the series").
- **AC-09**: **Given** Edit story opened from a book's story list (Edit book or an entry
  page), **When** it opens, **Then** it starts with "Back to “<book title>”", linking to
  where it came from. Opened another way, it links to the first book that contains the
  story.
- **AC-10**: **Given** the main navigation, **When** a page opens, **Then** the matching
  tab is marked as current:
  - **My books**: entry pages and My favorite authors;
  - **Catalog**: the Catalog page, every edit page, Summary, Add a story, series pages,
    author pages and Authors with no books;
  - **Import**: the import pages.

  The tab "Import from Open Library" now reads **Import**.
- **AC-11**: **Given** the Books added page after an import, **When** it opens, **Then** it
  also links to the Catalog.

---

### User Story 3 - Quicker ways to add the next book (Priority: P2)

From a series or an author, the member can start Add a book with the right details already
filled in.

**Why this priority**: it saves typing, but every flow already works without it.

**Acceptance Criteria**:

- **AC-12**: **Given** a series page whose highest book or story number is N, **When** it
  shows, **Then**:
  - after the last numbered row (before any books with no number) there is a row
    "#<next> Not in the family catalog yet · **Add #<next>**", where next is the next
    whole number after N;
  - **Add #<next>** opens Add a book with the series and that number filled in, returning
    to the series page (spec 006).

  The row is not shown when the next number would be over 999, or when the series has no
  numbered books or stories.
- **AC-13**: **Given** a series page, **When** it shows, **Then** it offers **Add a
  collection with stories in this series**. That opens Add a book with:
  - the series filled in and no number;
  - the anthology box ticked and one story row (spec 013);
  - a return to the series page after saving.
- **AC-14**: **Given** an author page, **When** it shows, **Then** it offers **Add a book by
  this author**, which opens Add a book with that author chosen. An unknown or malformed
  author id in the address opens the plain form.

---

### User Story 4 - Account safety (Priority: P2)

Every member can change their own password. An admin confirms before changing someone
else's account.

**Why this priority**: there's a working page nobody can find, and one-click admin
actions are easy to hit by mistake on a phone.

**Acceptance Criteria**:

- **AC-15**: **Given** any signed-in member, **When** any page shows, **Then** the account
  area beside **Switch user** and **Sign out** offers **Change password**, linking to the
  existing page.
- **AC-16**: **Given** Accounts, **When** the admin chooses **Deactivate**, **Make Admin**
  or **Reset password**, **Then**:
  - nothing changes yet;
  - a confirmation page names the member and the action ("Deactivate Ben? Ben won't be
    able to sign in until reactivated.");
  - it offers **Confirm** and **Cancel**.

  Confirm applies the action exactly as today. Cancel returns to Accounts with nothing
  changed. **Reactivate** and **Make Member** stay one step.
- **AC-17**: **Given** the Reset password confirmation, **When** it shows, **Then**:
  - it doesn't display the typed temporary password, and carries it in the form only;
  - an empty or invalid password is refused with today's messages, before the
    confirmation page.

---

### User Story 5 - Long pages on a phone (Priority: P3)

**Acceptance Criteria**:

- **AC-18**: **Given** My books, **When** it shows, **Then** the **My favorite authors**
  link sits with the filters, on its own line after Apply (books-349: inside the Author
  field it pushed that dropdown out of line), not below the list. Without JavaScript it
  is still reachable. On a phone it shows when "Sort and filter" is open.
- **AC-19**: **Given** an entry page, **When** it opens, **Then** a "Jump to" list near the
  top links to Book details, My reading and Stories in this book.

---

### User Story 6 - Usable everywhere (Priority: P2)

**Acceptance Criteria**:

- **AC-20**: **Given** every page changed here, **When** each is checked at phone, tablet
  and laptop widths (spec 003), **Then**:
  - there is no sideways scroll;
  - every control is at least 44 × 44 CSS px;
  - axe reports no WCAG 2.2 AA violations.
- **AC-21**: **Given** JavaScript is off, **When** a member uses every new link and
  button, **Then** it works as with JavaScript on.

### Edge Cases

- **Another member's entry:** back links and "Jump to" use only the viewer's own entry
  (Principle I). A book on someone else's list but not mine gets "Back to the catalog".
- **Add a story from an entry page for a book later removed from my list:** saving still
  adds the story (it's catalog data). Returning to an entry that no longer exists goes to
  Edit book instead.
- **A series with only unnumbered books:** no Add #next row (AC-12).
- **A series at #999:** no Add #next row.
- **The `from` address on Add or Edit story** names an entry or book that isn't the
  member's, or doesn't exist: it is ignored and the default return is used. It is never
  an open redirect: only internal paths built from ids are used.
- **An action today's rules refuse** (for example, demoting the last admin): the
  confirmation page still shows. On Confirm, Accounts shows today's error and nothing
  changes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every entry page MUST show a Stories in this book section with Add a story.
- **FR-002**: Add a story MUST offer Add and add another. Add story and Add a story MUST
  return to where they were opened from (an entry page or Edit book).
- **FR-003**: Edit book, Edit series, Edit story and Summary MUST each have a link back,
  as AC-06 to AC-09 describe.
- **FR-004**: The main navigation MUST mark the related tab on every page (AC-10), and the
  Import tab MUST read "Import".
- **FR-005**: Series pages MUST offer Add #next (AC-12) and Add a collection with stories
  in this series (AC-13). Author pages MUST offer Add a book by this author (AC-14).
- **FR-006**: Add a book MUST accept `anthology=yes` (the box ticked) and `author=<id>`
  (that author chosen) in its address. Unknown values are ignored.
- **FR-007**: Every page MUST show Change password for the signed-in member.
- **FR-008**: Deactivate, Make Admin and Reset password MUST ask for confirmation first.
  Without it nothing changes.
- **FR-009**: My books MUST show the favorite-authors link with the filters, after Apply
  (books-349). Entry pages and Edit book MUST have jump links.
- **FR-010**: Every change MUST work without JavaScript, keep CSRF protection on posts, and
  meet WCAG 2.2 AA and the spec 003 layouts.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Stories (added from an entry page) | Catalog | All members | Any member |
| Back links' "my entry for this book" | Personal (read only) | Owner only | — |

- **Duplication check**: none. Nothing new is stored.
- **Cross-user access**: back links and jump links look up only the viewer's own entry.

## AI Involvement *(mandatory)*

- **Generated content**: None.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: None.
- **Sent to external services**: None.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From any edit page or the Summary page, a member reaches where they came from
  in one tap.
- **SC-002**: A member can turn a book on their list into a three-story collection, from its
  entry page, in under two minutes, without visiting the Catalog.
- **SC-003**: No admin account change happens from a single tap.
- **SC-004**: Every changed page stays within the existing 1 s budget (p95) with 5,000
  books.

## Assumptions

- **"Related tab" mapping** is as in AC-10. Series and author pages count as Catalog,
  because they show the shared catalog with my statuses.
- **Add #next** looks only at numbers in this series (books and stories). It ignores
  fractional gaps (#2.5 doesn't make #3.5).
- **Confirmation pages**, not JavaScript dialogs, so they work without JavaScript and with
  screen readers.
- **Reactivate and Make Member** are easy to undo and stay one step, as before.
- The other UI-review beads (books-d9u read-only book page, books-1kx separate saves,
  books-1q7 rows and quick add) are separate. Some of these links may later point at the
  read-only book page instead.
