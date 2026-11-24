# Feature Specification: Read-only Book Page

**Feature Branch**: `016-book-page`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "Read-only book page; book titles link to it (bead books-d9u,
from the 2026-11-23 UI flow review)."

Today, a book's title goes to different places:
- in the Catalog, on author pages, and in the Edit author and Edit series book lists, a
  book not on my list opens Edit book, the shared form that changes the family catalog;
- some titles aren't links at all: series rows for books not on my list, and a story's
  containing books on a series page.

No page shows a catalog book's details (summary, stories, series, authors) unless the book
is on my list. A member who only wants to look at a book lands on a form.

Decisions made with the user on 2026-11-23:
- **Titles:** everywhere except My books, a title opens the book page, and the status
  badge still opens my entry. On My books, my own list, the title keeps opening my entry.
- **Stories:** on a collection's page, each story shows its place ("#4.5 Discworld — Troll
  Bridge", the series linked), plus "Also in “<book>”" for each other book that contains
  it, linking to that book's page.

## Overview

This feature adds a read-only page for every catalog book. It shows:
- the book's details;
- its summary;
- its stories;
- where I am with it;
- the ways to add it to my list, open my entry or edit it.

Book titles across the app link to it, so looking at a book never means opening a form.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Look at any book (Priority: P1)

Browsing the Catalog, a member taps *Small Gods*, which isn't on their list. A page shows
the authors, "Discworld #13", the summary and who wrote it. From there they tap **Want to
read** and stay on the page, which now shows **Want to read** and **Open my entry**.

**Why this priority**: it's the new capability. Linking the titles (User Story 2) needs it.

**Independent Test**: open the book page for a book on my list and one that isn't. Check
the details, the summary, my status and the actions on each.

**Acceptance Criteria**:

- **AC-01**: **Given** a catalog book, **When** a signed-in member opens its book page,
  **Then** it shows, in this order:
  1. the title as the page heading;
  2. the authors, each linking to their author page (with "pen name of …" as on the
     entry page);
  3. the series and number ("Discworld #13", or the series name alone), linking to the
     series page, when the book is in a series;
  4. the release information as on the entry page (spec 007): "Coming <date>" while
     upcoming, "Released <date>" once out, and nothing without a date;
  5. the source reference when the book was imported (spec 008), as on the entry page.

  It contains no form fields that change the book.
- **AC-02**: **Given** the book has a current summary, **When** its page shows, **Then** it
  shows the summary text with "Written by <name> on <date>". **Given** it has none,
  **Then** it says "No summary yet." Either way it offers **Write a summary** (or **Write a
  new summary**) and **Draft with AI**, as the entry page does. Nothing AI-generated is
  stored until a member accepts it (Principle III, spec 012).
- **AC-03**: **Given** the book is on my list, **When** its page shows, **Then** it shows my
  status as the spec 015 badge linking to my entry, with any finished date, and an **Open
  my entry** link. **Given** it isn't on my list, **Then** it says "Not on my list" with
  the spec 015 **Want to read** button and the **Add with details…** link.
- **AC-04**: **Given** I choose **Want to read** on the book page, **When** the request
  completes, **Then** the book is on my list as Want to read, I return to the book page,
  and the spec 015 notice shows ("Added “<title>” to your list as Want to read.", or
  "“<title>” is already on your list."). **Add with details…** opens Add a book with this
  book chosen.
- **AC-05**: **Given** any book page, **When** it shows, **Then** it offers **Edit book**
  (the shared edit form, as today) and links to all of the author's books and to the
  series page.
- **AC-06**: **Given** a book id that doesn't exist, **When** its page is requested,
  **Then** the answer is Not Found. An id that isn't a valid id is refused (Not Found or
  Unprocessable, as for series pages). **Given** a member who isn't signed in,
  **Then** they are sent to sign in, as for every other page.

---

### User Story 2 - Titles open the book page (Priority: P1)

Wherever a book is listed, other than my own list, its title opens the book page.

**Why this priority**: without it, the new page is hard to find, and titles keep leading to
an edit form.

**Independent Test**: on each listed page, follow a title for a book on my list and one
that isn't, and check both reach the book page. Then check a My books title still opens my
entry.

**Acceptance Criteria**:

- **AC-07**: **Given** a book row, **When** it shows on any of these pages, **Then** its
  title links to that book's page, whether or not the book is on my list:
  - the Catalog;
  - author pages;
  - Upcoming, both "On my list" and "Also coming in the family catalog";
  - series pages: book rows, and each containing book named on a story row;
  - the book lists on Edit author and Edit series.

  The status badge, where shown, still opens my entry (spec 015).
- **AC-08**: **Given** My books, **When** a row shows, **Then** its title opens my entry, as
  today. The "Now out" list at the top of My books also keeps opening my entry.
- **AC-09**: **Given** my entry page or the Edit book page, **When** it shows, **Then** it
  links to the book page ("View the book page").
- **AC-10**: **Given** a quick add (spec 015) posted from the book page, **When** it
  redirects, **Then** the book page is an accepted return address. Any other address is
  still refused and returns to the Catalog (spec 015 AC-05).

---

### User Story 3 - Collections and their stories (Priority: P2)

On a collection's page, a member sees each story's place in its series, and the other books
that contain it.

**Why this priority**: it gives a collection's stories a read-only home (books-1a5). Most
books have no stories.

**Independent Test**: make a collection with two stories, one of which is also in another
book. Check that both stories show with their series place, and that the shared one says
"Also in “<other book>”", linking to that book's page.

**Acceptance Criteria**:

- **AC-11**: **Given** a book with stories, **When** its page shows, **Then** a "Stories in
  this book" section lists each one as on the entry page: "#n Series — Title", the series
  linking to its series page, in the same order. **Given** a story that's also in other
  books, **Then** its line adds "Also in “<book>”" for each, linking to that book's page.
  The book itself is not listed there.
- **AC-12**: **Given** a book with no stories, **When** its page shows, **Then** the section
  says no stories are recorded and offers **Add a story** (spec 014), which returns to the
  book page afterwards.

---

### User Story 4 - Private, accessible and fast (Priority: P2)

**Acceptance Criteria**:

- **AC-13**: **Given** another member has the book on their list (with any status, notes or
  rating), **When** I open the book page, **Then** nothing of theirs shows: no status, no
  dates, no notes, no "also read by". Only my own entry is used (Principle I).
- **AC-14**: **Given** the book page, with the book on and off my list, with a summary and
  stories, and with the quick-add notice, **When** it's checked at phone, tablet and
  laptop widths (spec 003), **Then**:
  - there is no sideways scroll;
  - every button and link is at least 44 × 44 CSS px;
  - axe reports no WCAG 2.2 AA violations;
  - a keyboard user can reach every action in reading order.
- **AC-15**: **Given** a catalog of 5,000 books, **When** the book page for a book with 50
  stories shows, **Then** it stays within the 1 s budget (p95). The Catalog, author and
  series pages stay within their budgets after the link changes.

### Edge Cases

- **A story that is also a book on its own:** stories are a separate kind of record (spec
  009), so a story line never links to a book page except through "Also in".
- **A book removed from my list while its page is open:** the page shows "Not on my list"
  on its next load, and the quick add works as usual.
- **A book whose author was renamed or merged:** the page shows the current names, as every
  other page does.
- **The Edit book page's back link:** it keeps going back to my entry when the book is on my
  list (spec 014 AC-06), and to the Catalog otherwise.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every catalog book MUST have a read-only page that any signed-in member can
  open. It shows the book's details, current summary, stories and the viewer's own status
  (AC-01–AC-03, AC-11).
- **FR-002**: The book page MUST offer the actions the viewer needs next: **Want to read**
  and **Add with details…**, or **Open my entry**; **Edit book**; and the summary actions
  (AC-02–AC-05).
- **FR-003**: Book titles on the Catalog, author pages, Upcoming, series pages and the Edit
  author and Edit series book lists MUST open the book page. Titles on My books MUST keep
  opening my entry (AC-07, AC-08).
- **FR-004**: The quick add MUST accept the book page as a return address, and refuse every
  other address it doesn't already allow (AC-10).
- **FR-005**: The book page MUST use only the viewer's own entry (Principle I, AC-13).
- **FR-006**: A missing book MUST return Not Found (AC-06).
- **FR-007**: The page MUST meet WCAG 2.2 AA and the spec 003 layouts, and keep the
  5,000-book budgets (AC-14, AC-15).

### Key Entities

- No new entities. The page reads the catalog book, its authors, series, current summary
  and stories, plus the viewer's own reading entry.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Book, authors, series, summary, stories | Catalog | All members | — (read-only here) |
| My status and finished date on the book page | Personal | Owner only | — (read-only here) |
| The entry from a quick add on the book page | Personal | Owner only | Owner only |

- **Duplication check**: none. The page reads catalog data in place.
- **Cross-user access**: none. Another member's entries are never read for this page.

## AI Involvement *(mandatory)*

- **Generated content**: none new. The **Draft with AI** link starts the existing spec 012
  draft flow, whose review step is unchanged.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: none.
- **Sent to external services**: none.

## API Changes

- **New endpoints**: none. The JSON API already has `GET /api/v1/books/{book_id}`. The book
  page is an HTML page only.
- **Breaking changes**: none.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From any list other than My books, a member can read a book's summary in one
  tap, without opening a form.
- **SC-002**: No book title on the Catalog, author pages, Upcoming or series pages opens
  the edit form.
- **SC-003**: The book page shows within 1 s (p95) at 5,000 books, including a book with 50
  stories.

## Assumptions

- **My entry page is unchanged** apart from its link to the book page. It stays the place
  to change my reading and the book's details.
- **The book page is at `/books/<id>`**, next to the existing `/books/add` and the spec 015
  quick add.
- **Story titles aren't links.** A page per story is out of scope. Story edits stay on Edit
  book and the story edit page.
- **The admin-only and import pages** (Import, Unused authors) keep their current links.
- **No editing on the book page:** every change goes through Edit book, my entry or the
  summary page.
