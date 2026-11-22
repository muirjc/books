# Feature Specification: Delete an Author With No Books

**Feature Branch**: `008-delete-unused-authors`

**Created**: 2026-11-21

**Status**: Implemented

**Input**: User description: "books-4oc: let a member delete a catalog author that no book is
linked to. Example: 'J DM Robb' (0 books), a mistyped duplicate of 'J.D. Robb'. Offer
Delete author only when no book is linked, otherwise explain why and point to the books;
confirm first; check 'no books' in the same transaction as the delete; any member may
delete an unlinked author; consider a list of authors with no books so they can be found."

## Overview

A mistyped author (such as "J DM Robb") can end up in the family catalog with no books. It
then shows in the author type-ahead on Add a book, where it invites more mistakes, and
nobody can remove it: the Edit author page can only rename.

This feature adds:

- **Authors with no books**: a page listing them, linked from My books whenever there is
  at least one, because an author with no books appears on nobody's list and can't
  otherwise be reached.
- **The author's books on Edit author**: the page lists the books linked to the author, so
  a member can see what depends on it.
- **Delete author** on Edit author, offered only when no book is linked, with a confirm
  step. An author with books says why it can't be deleted.

The catalog is shared (Principle II): any member may delete an author no book uses. No
personal data is involved.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find and delete an author with no books (Priority: P1)

**Why this priority**: this is the request: remove "J DM Robb".

**Independent Test**: With one author with no books and one with books, follow the link
from My books, open the author, delete it and confirm; it's gone from the catalog and the
type-ahead.

**Acceptance Criteria**:

- **AC-01**: **Given** at least one catalog author has no books, **When** a member opens My
  books, **Then** the page shows a link "Authors with no books (N)"; with none, the link is
  not shown.
- **AC-02**: **Given** the Authors with no books page, **When** it is opened, **Then** it
  lists every author with no linked book, by sort name, each linking to Edit author; with
  none it says "Every author in the family catalog has at least one book."
- **AC-03**: **Given** Edit author for an author with no books, **When** the member chooses
  **Delete author**, **Then** a confirm page asks "Delete “J DM Robb” from the family
  catalog?" with **Delete** and **Cancel**; nothing is deleted yet.
- **AC-04**: **Given** the confirm page, **When** the member chooses **Delete**, **Then** the
  author is removed from the catalog, and the member lands on the Authors with no books
  page with the message "Deleted “J DM Robb”." The author no longer appears in the
  type-ahead, and its Edit author page gives Not Found.
- **AC-05**: **Given** the confirm page, **When** the member chooses **Cancel**, **Then** they
  return to Edit author and nothing changes.

### User Story 2 - An author with books can't be deleted (Priority: P1)

**Acceptance Criteria**:

- **AC-06**: **Given** Edit author for an author with books, **When** it is shown, **Then**
  it lists those books (title, linking to the book's Edit book page) and says "This
  author can't be deleted while books list them. Change those books' authors first." No
  Delete author button is shown.
- **AC-07**: **Given** a member is on the confirm page, **When** another member links a book
  to the author before Delete is chosen, **Then** nothing is deleted, and Edit author is
  shown again with the message "“J DM Robb” now has a book, so it wasn't deleted."
- **AC-08**: **Given** a delete request for an author that doesn't exist (or was just
  deleted by someone else), **When** it is sent, **Then** the member gets Not Found.

### User Story 3 - Usable everywhere (Priority: P2)

- **AC-09**: **Given** the Authors with no books page, Edit author with its book list, and
  the confirm page, **When** they are checked at phone, tablet and laptop widths (spec
  003), **Then** there is no sideways scroll, every link and button is at least 44 × 44 CSS
  px, and axe reports no WCAG 2.2 AA violations; the flow works without JavaScript.

### Edge Cases

- **Pen names:** an author used as someone's real name is plain text, not a link, so
  deleting an author never affects another author.
- **Delete via the confirm form without "confirm":** shows the confirm page, never deletes
  (as Remove from my list).
- **Two members deleting at once:** the second gets Not Found (AC-08).
- **Imported books' source links** reference books, not authors; unaffected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST list catalog authors that no book is linked to, and link to
  that list from My books when it isn't empty, showing the count.
- **FR-002**: Edit author MUST list the books linked to the author.
- **FR-003**: Any member MUST be able to delete an author that no book is linked to, after
  confirming; the check and the delete MUST happen together, so an author that gains a
  book first is not deleted and the member is told why.
- **FR-004**: An author with books MUST NOT be deletable, through the pages or the JSON API.
- **FR-005**: The JSON API MUST offer deleting an author (`204`, `404` unknown, `409` while
  books are linked), as an additive change.
- **FR-006**: The pages MUST work without JavaScript and meet WCAG 2.2 AA and the spec 003
  layouts.

### Key Entities

- **Author (catalog)**: unchanged; can now be deleted when no book is linked.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Author, its linked books | Catalog | All members | Any member (delete only when unlinked) |

- **Duplication check**: N/A; nothing is copied.
- **Cross-user access**: none; no personal records are read or written.

## AI Involvement *(mandatory)*

- **Generated content**: None.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: None. The server log records which member id deleted
  which author id.
- **Sent to external services**: None.

## API Changes *(include if feature changes the JSON API)*

- **New endpoints**: `DELETE /api/v1/authors/{author_id}`.
- **Breaking changes**: None.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From My books, a member can delete an author with no books in four actions
  (open the list, open the author, Delete author, Delete).
- **SC-002**: No author with a linked book can be deleted by any path (tests cover the
  pages, the race and the API).
- **SC-003**: The Authors with no books page and My books load within the existing budget
  (under 1 s at p95) with 1,500 authors and 5,000 books.

## Assumptions

- **Where the list is linked:** from My books, shown only when there is something to tidy,
  so it stays out of the way.
- **No undo:** an author with no books holds only a name, sort name and pen-name details;
  retyping it is the undo.
- **No merge feature:** fixing a duplicate author that *has* books (moving books to the
  right author) is done through Edit book today and is out of scope.
- **Audit:** there is no audit table; an info line in the server log records the member id
  and author id.
