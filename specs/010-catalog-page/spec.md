# Feature Specification: Catalog Page

**Feature Branch**: `010-catalog-page`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "Catalog page: browse and search all family catalog books"
(bead books-5hf). Members can only reach the shared catalog indirectly: the type-ahead on
Add a book, series pages, and the author and series edit pages. There is no page to browse
or search every catalog book. Add a Catalog page listing all catalog books (title, authors,
series and number, Coming date), with search by title, author, real name or ISBN, sort and
paging. Each book links to its catalog page and offers **Add to my list** (the spec 006
`/books/add?book=` start), or **On my list** for the viewer's own entries.

## Overview

The family catalog holds every book any member has added or imported. Today a member sees
it only through other pages: suggestions while typing on Add a book, the rows of one
series, or the books listed on one author's edit page.

This feature adds a **Catalog** page, reached from the main navigation, that lists every
catalog book. A member can search it, sort it, page through it and add any book to their own
list from it. The page shows catalog data. The only personal data on it is the viewer's
own: whether each book is on their list.

### Example

A member searches the catalog for "dresden", sorted by series:

| Book | Shows |
|---|---|
| Storm Front | Jim Butcher · The Dresden Files #1 · **On my list** |
| Fool Moon | Jim Butcher · The Dresden Files #2 · **Add to my list** |
| Twenty Lives | Jim Butcher · The Dresden Files #18 · Coming 3 Mar 2027 · **Add to my list** |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse the whole family catalog (Priority: P1)

A member opens **Catalog** from the main navigation and sees every book in the family
catalog, a page at a time. Each row shows the title, authors, series and number, and the
Coming date while the book isn't out yet. The title opens the book's catalog page (Edit
book), and the series opens its series page.

**Why this priority**: the catalog can't be seen as a whole today. A list alone is the
smallest useful slice.

**Independent Test**: with 120 catalog books, open Catalog; check the first 50 by title, the
count, and the links; page to 3; sign out and check the page is refused.

**Acceptance Criteria**:

- **AC-01**: **Given** a signed-in member, **When** they view any page, **Then** the main
  navigation has a **Catalog** link, marked as the current page while on the Catalog page.
- **AC-02**: **Given** a signed-out visitor, **When** they request the Catalog page, **Then**
  they are sent to sign in, as for other member pages. A member who must change their
  password is sent to change it, as elsewhere.
- **AC-03**: **Given** a catalog of books, **When** a member opens the Catalog page, **Then**
  it shows "N books in the family catalog" and lists the books by title (A–Z, ignoring case).
  Each row has the title, the authors in order, and the series and number when the book has
  them.
- **AC-04**: **Given** a book released after today, **When** it is listed, **Then** its row
  shows "Coming <date>". A book that is already out shows no release text.
- **AC-05**: **Given** a listed book, **Then** its title links to the book's catalog page
  (Edit book), and its series, when it has one, links to the series page.
- **AC-06**: **Given** more than 50 matching books, **When** the page is shown, **Then** it
  lists 50 per page with **Previous**, "Page n of m" and **Next** links. The links keep the
  search, sort and filter, and a page number past the end shows the last page. An invalid
  page number shows page 1.
- **AC-07**: **Given** an empty catalog, **When** a member opens the page, **Then** it says
  "The family catalog is empty." with a link to Add a book.

---

### User Story 2 - Add a catalog book to my list (Priority: P1)

While browsing, a member sees which books are already on their own list and can start adding
any other book in one step.

**Why this priority**: adding a book that someone else already catalogued is the main reason
to browse.

**Independent Test**: as Member A with one of three books on their list, open Catalog; check
that book shows **On my list** linking to the entry and the others show **Add to my list**.
As Member B, who has a different book, check A's book shows **Add to my list**.

**Acceptance Criteria**:

- **AC-08**: **Given** a book on the viewer's list, **When** it is listed, **Then** its row
  shows **On my list**, linking to the viewer's entry page.
- **AC-09**: **Given** a book not on the viewer's list, **When** it is listed, **Then** its
  row has an **Add to my list** link to Add a book started from that book (spec 006). Its
  accessible name includes the title, as in "Add “Fool Moon” to my list".
- **AC-10**: **Given** another member has a book on their list, with any status, rating or
  notes, **When** the viewer opens the Catalog page, **Then** nothing on the page or in its
  responses shows that: the row reads exactly as for a book no member has (Principle I).

---

### User Story 3 - Search, sort and filter the catalog (Priority: P2)

A member searches the catalog by what they remember (a title, an author, an author's real
name, a story in a collection, or an ISBN), sorts the results, and can hide the books
already on their list.

**Why this priority**: browsing 5,000 books by title alone is slow; search makes the page
practical.

**Independent Test**: search "butcher", "Restoration" (a story in *Side Jobs*) and an ISBN;
sort by author and by newest; tick **Not on my list**; all without JavaScript, then with it.

**Acceptance Criteria**:

- **AC-11**: **Given** a search term, **When** the member searches, **Then** the list shows
  the books whose title, author name, author real name, series name or story title (spec
  009) contains the term, ignoring case. The count reads "N books match". Up to 200
  characters are used.
- **AC-12**: **Given** a search for a valid ISBN-13, written with or without hyphens or
  spaces, **When** a book has that ISBN, **Then** that book is listed, first. (The catalog
  stores ISBN-13 only, as the existing search does.)
- **AC-13**: **Given** the sort list, **When** the member picks one, **Then** the list is
  ordered by it: Title (A–Z), Title (Z–A), Author (the first author's sort name, then title),
  Series (series name, then number, with books not in a series last, then title) or Newest
  in the catalog (most recently added first). An unknown sort shows Title (A–Z).
- **AC-14**: **Given** **Not on my list** is ticked, **When** the list is shown, **Then** it
  leaves out the books on the viewer's own list, and only those.
- **AC-15**: **Given** a search or filter with no matches, **When** the list is shown,
  **Then** it says "No catalog books match." with a link that clears the search.
- **AC-16**: **Given** JavaScript is off, **When** the member submits the form, **Then** the
  full page reloads with the results. With JavaScript on, the list updates in place as they
  type or change a control, the address keeps the search, and the results are announced to
  screen readers.

---

### Edge Cases

- **A search with characters that have meaning in patterns** (`%`, `_`, `\`): they are
  matched as typed (the existing search rules).
- **A book removed from the catalog while a member pages**: the next page simply lists what
  remains. Paging uses the order of the current request.
- **A book with no authors**: this can't happen. Every catalog book has at least one author.
- **The same story title in many books**: each book is listed once.
- **Another member's records**: the page reads only the viewer's own entries, so there is no
  other member's record to request. Entry links go to the viewer's own entries.
- **Phone width**: rows stack in the spec 003 list layout. The sort and filter controls fold
  behind **Sort and filter**, as on My books.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a Catalog page, reachable from the main navigation,
  to any signed-in member, and refuse it to signed-out visitors (AC-01, AC-02).
- **FR-002**: The page MUST list every catalog book, 50 per page, with its title, authors,
  series and number, and Coming date (AC-03 – AC-07).
- **FR-003**: Each row MUST show **On my list** for the viewer's own entry, or offer **Add
  to my list** (AC-08, AC-09).
- **FR-004**: The page MUST NOT reveal any other member's entries, statuses, dates, ratings or
  notes, including through counts, filters or ordering (AC-10, AC-14).
- **FR-005**: The page MUST support search, sort and a **Not on my list** filter, and keep
  them across pages (AC-06, AC-11 – AC-15).
- **FR-006**: The page MUST work without JavaScript, update in place with it (AC-16), meet
  WCAG 2.2 AA, and follow the spec 003 layouts at phone, tablet and desktop widths.
- **FR-007**: The page MUST meet the 5,000-book performance budgets (SC-001).

### Key Entities

No new entities. The page reads existing catalog **Books**, with their **Authors**,
**Series** and **Stories** (search only), and the viewer's own **Reading entries** (which
books are on their list).

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Book title, authors, series, number, release date, ISBN, date added | Catalog | All members | Not written here |
| Story titles (search only) | Catalog | All members | Not written here |
| Whether a book is on my list, and my entry's id | Personal | Owner only | Not written here |

- **Duplication check**: nothing is stored. The page only reads.
- **Cross-user access**: "on my list", the entry links and the **Not on my list** filter use
  only the session user's entries, filtered in the data-access layer. No other member's
  personal data is read.

## AI Involvement *(mandatory)*

- **Generated content**: None.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: None.
- **Sent to external services**: None.

## API Changes

None. The existing catalog book search in the JSON API is unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With 5,000 catalog books, 2,000 of them on the viewer's list, the Catalog page
  loads in under 1 second at p95, for the plain list, a search, each sort, the **Not on my
  list** filter, and a late page.
- **SC-002**: A member can find a catalog book by any one of its title, author, author's
  real name, series, story or ISBN, and start adding it to their list, from one page.
- **SC-003**: Automated accessibility checks report no WCAG 2.2 AA violations on the page at
  phone, tablet and desktop widths, and the search, sort, paging and add journeys work by
  keyboard alone.

## Assumptions

- **The catalog page of a book is Edit book** (`/catalog/books/{id}/edit`). There is no
  separate read-only book page, and adding one is out of scope.
- **The address is `/catalog`.** It sits next to the existing `/catalog/…` edit pages. In the
  navigation, **Catalog** comes after **Add a book**.
- **"Newest in the catalog"** means when the book was added to the catalog, not its release
  date. Release order is the Upcoming page's job (spec 007).
- **Search matches the same fields as My books and Add a book together**: title, author name,
  real name, series name, story title and exact ISBN. The Add a book type-ahead is unchanged.
- **The Not on my list filter** is the one filter offered. Author and series filters already
  exist on the author and series pages, and a status filter would mean nothing for books not
  on the list.
- **Catalog editing stays where it is**: the page links to Edit book and adds nothing new to
  editing.
- **No API change**: the JSON API's catalog search already covers clients that need it.
