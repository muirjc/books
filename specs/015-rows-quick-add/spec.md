# Feature Specification: Consistent Book Rows and Quick "Want to read"

**Feature Branch**: `015-rows-quick-add`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "Consistent list rows and a quick 'Want to read' add (bead
books-1q7, from the 2026-11-23 UI review)."

Today the lists show the same book in different ways:
- status is a badge in some lists and plain text in others;
- the Catalog shows "On my list" rather than my status;
- series numbers and release dates sit in different places;
- the Author page drops the series name from each row.

The proposal is one shared row, plus a one-click "Want to read" on rows, keeping the full
Add a book form for details.

Decisions made with the user on 2026-11-23:
- rows for books not on my list offer both a one-click **Want to read** and **Add with
  details…**;
- the one-click add is on the Catalog, author pages, Upcoming and series pages.

## Overview

A member browsing the family catalog often just wants to remember a book for later. Today
that means opening Add a book, checking the status, and saving. Each list also shows a
book differently, so "is this on my list, and where am I with it?" takes a different
glance on every page.

This feature:
- gives the Catalog, author pages and Upcoming one row layout:
  - the title;
  - one details line: authors, series and number, release label;
  - **my status** as a badge, or "Not on my list";
  - one place for actions;
- shows my status as the same badge on series pages;
- adds a one-click **Want to read** to every row whose book isn't on my list, on all four
  pages. It adds the book to my list as Want to read and keeps me on the same page, at
  the same row;
- keeps **Add with details…** beside it, for the full form.

My books keeps its own columns (finished date, times read). Its status badge already
matches.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Remember a book in one click (Priority: P1)

Browsing the Catalog, a member sees *Small Gods* and taps **Want to read**. The page comes
back at the same place, the row now shows **Want to read**, and a notice confirms it.

**Why this priority**: it's the new capability; the consistency work supports it.

**Independent Test**: on the Catalog, filtered to an author and on page 2, tap **Want to
read** on a row. Check:
- the entry exists with status Want to read;
- the page returns with the same filters and page, at that row;
- the notice shows.

**Acceptance Criteria**:

- **AC-01**: **Given** a row on the Catalog, an author page, Upcoming ("Also coming in the
  family catalog") or a series page for a book not on my list, **When** the page shows,
  **Then** the row offers a **Want to read** button and an **Add with details…** link.
  The link opens Add a book with that book chosen, as today (spec 006); from a series
  page, it returns there afterwards.
- **AC-02**: **Given** I choose **Want to read**, **When** the request completes, **Then**:
  - the book is added to my list with status Want to read, with no finished date, notes
    or pre-order;
  - I return to the same page, with the same filters, sort and page number, scrolled to
    that book's row;
  - a notice says "Added “<title>” to your list as Want to read." and links to my entry.
- **AC-03**: **Given** the book is already on my list (another tab, or a double tap),
  **When** I choose **Want to read**, **Then** nothing changes. I return as in AC-02 with
  the notice "“<title>” is already on your list."
- **AC-04**: **Given** a story row on a series page whose containing book isn't on my list,
  **When** the page shows, **Then** for each containing book there is a **Want to read**
  button, named for that book ("Want to read “Side Jobs”"), and an **Add with details…**
  link. The button adds the containing book.
- **AC-05**: **Given** a book id that doesn't exist, **When** **Want to read** is posted,
  **Then** the answer is Not Found. **Given** a return address that isn't one of these
  four pages (another site, a scheme, `//host`, or any other path), **When** it's posted,
  **Then** the book is still added, and I return to the Catalog.
- **AC-06**: **Given** JavaScript is off, **When** I use **Want to read**, **Then** it works
  the same, as a normal form post.

---

### User Story 2 - One row layout, with my status everywhere (Priority: P2)

On the Catalog, author pages and Upcoming, every row reads the same way and shows where I
am with the book.

**Why this priority**: it makes lists scannable, but nothing is broken without it.

**Independent Test**: put one book on my list as Reading. Check the Catalog, its author
page and Upcoming (if it's coming) each show the title, the same details line and a
**Reading** badge linking to my entry.

**Acceptance Criteria**:

- **AC-07**: **Given** a book row on the Catalog, an author page or Upcoming, **When** it
  shows, **Then** it reads in this order:
  1. the title;
  2. the details line: authors, then "Series #n" (or the series name alone), then the
     release label (spec 007) when there is one;
  3. my status;
  4. the actions.

  Author pages show the series and number on each row as well as in the group heading.
- **AC-08**: **Given** a book on my list, **When** its row shows on those pages, **Then** my
  status is a badge ("Want to read", "Reading" or "Finished") linking to my entry, named
  for the book for screen readers, replacing "On my list". **Given** a book not on my
  list, **Then** the row says "Not on my list" in plain text, followed by the AC-01
  actions.
- **AC-09**: **Given** a series page, **When** a book row shows my status, **Then** the
  status is the same badge as on the other pages (a story row's derived status too), with
  any finished date after it as today.
- **AC-10**: **Given** the title link, **When** the book is on my list, **Then** it opens my
  entry; **otherwise** it opens Edit book as today. (books-d9u may later point it at a
  read-only book page.)
- **AC-11**: **Given** another member's entries, **When** any row shows, **Then** only my
  own status is used. Another member's reading never shows (Principle I).

---

### User Story 3 - Usable everywhere (Priority: P2)

**Acceptance Criteria**:

- **AC-12**: **Given** the Catalog, an author page, Upcoming and a series page, with rows on
  and off my list and the quick-add notice, **When** each is checked at phone, tablet and
  laptop widths (spec 003), **Then**:
  - there is no sideways scroll;
  - every button and link is at least 44 × 44 CSS px, including the spec 007 Upcoming
    checks;
  - axe reports no WCAG 2.2 AA violations.
- **AC-13**: **Given** a screen reader, **When** it reads a row, **Then** it hears:
  1. the title;
  2. the details;
  3. the status;
  4. buttons named for the book: "Want to read “Small Gods”" and "Add “Small Gods” with
     details".
- **AC-14**: **Given** the Catalog with 5,000 books, **When** a page of rows shows, **Then**
  it stays within the 1 s budget (p95), and a quick add redirect completes within it too.

### Edge Cases

- **Filters change the list:** after a quick add on the Catalog filtered to "Not on my
  list" (if such a filter exists), the book may no longer be in the results. The notice
  still confirms it.
- **The last item on a page:** the page number is kept even if the list shrinks. An empty
  page shows the usual message.
- **HTMX-updated Catalog lists:** quick-add buttons rendered in an HTMX response carry the
  current filters in their return address, the same as a full page.
- **Pre-ordered or upcoming books:** a quick add sets Want to read with Pre-ordered off.
  The Coming label shows as today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A member MUST be able to add a catalog book to their own list as Want to
  read with one action from the Catalog, author pages, Upcoming and series pages. The
  action works without JavaScript and is CSRF-protected.
- **FR-002**: After a quick add, the member MUST return to the page they were on, with its
  filters and page number, at the book's row, and see a confirmation. Return addresses
  MUST be limited to those four pages.
- **FR-003**: A quick add for a book already on the list MUST change nothing and say so.
- **FR-004**: The Catalog, author pages and Upcoming MUST use one row layout (AC-07), with
  my status as a badge linking to my entry, or "Not on my list" with the two actions.
- **FR-005**: Series pages MUST show my status with the same badge.
- **FR-006**: Rows MUST use only the viewer's own entries.
- **FR-007**: Every change MUST meet WCAG 2.2 AA and the spec 003 layouts, and keep the
  5,000-book budgets.

### Key Entities

- No new entities. A quick add creates a normal reading entry (status Want to read).

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| The new entry from a quick add | Personal | Owner only | Owner only |
| Status badges on rows | Personal (read) | Owner only | — |

- **Duplication check**: none. A quick add references the catalog book.
- **Cross-user access**: none. Entries are created and read only for the session member.

## AI Involvement *(mandatory)*

- **Generated content**: None.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: None beyond the entry the member asks for.
- **Sent to external services**: None.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Adding a book to my list as Want to read from the Catalog takes one tap and no
  page change, where today it takes three steps.
- **SC-002**: On the Catalog, author pages and Upcoming, my status for every book on my list
  is visible on its row.
- **SC-003**: The changed pages stay under 1 s (p95) at 5,000 books.

## Assumptions

- **My books is unchanged**: it is my list, with its own columns, and its badge already
  matches.
- **Series pages keep their number-first layout** (spec 006). Only the status badge and
  the actions change.
- **The quick add's return address** is a path on one of the four pages, with its query
  string, checked against an allow-list. The row's id (`book-<id>`) is the anchor.
- **No HTMX row swap**: a normal post and redirect is simple, works without JavaScript,
  and returns to the same row.
