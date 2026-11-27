# Feature Specification: Personal Rating

**Feature Branch**: `020-personal-rating`

**Created**: 2026-11-27

**Status**: Draft

**Input**: User description: "Personal rating 1–5 (bead books-xmr; product spec FR-17, data
model reading_entry.rating smallint nullable 1–5). A member can give each book in their own
list an optional rating from 1 to 5, or clear it. The rating is personal. Set it on the entry
page and on Add a book, shown on My books rows, with optional sort by rating and a filter by
rating on My books. Works with JavaScript off. JSON API: the reading entry schemas gain an
optional nullable rating. The schema change must be reversible. WCAG 2.2 AA, spec 003 widths
and 44 px targets, and the 5,000-book performance budgets apply."

The product specification lists a personal rating from 1 to 5 (FR-17, a "Could"), and its
data model has a rating on each reading entry. Neither was built: today a member can record
a book's status, dates, times read and private notes, but not how much they liked it.

## Clarifications

### Session 2026-11-27

- Q: Which books on a member's list can be rated? → A: Any status (Want to read, Reading or
  Finished); changing the status keeps the rating (AC-05).
- Q: What should the rating filter on My books offer? → A: "N and up": Any rating, 5, 4 and
  up, 3 and up, 2 and up, Rated, Not rated (AC-09).
- Q: If the change is undone after members have rated books, what happens to the ratings?
  → A: The undo works and removes them; the backup taken before every deploy keeps them
  (AC-13).

## Overview

After this feature:
- **Each entry on a member's list may have a rating** from 1 to 5, or no rating. It starts
  with none.
- **The rating is the member's own**, like their status and notes. No other member ever
  sees it.
- **A member sees their ratings** on My books, on their entry and on the book page, and can
  sort and filter My books by them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Rate a book (Priority: P1)

A member finishes *The Hobbit*, opens their entry, chooses **4** for Rating and saves. Later
they change it to 5, or clear it.

**Why this priority**: it's the bead: there's nowhere to record how much a member liked a
book.

**Independent Test**: rate an entry 4 on its entry page, check it shows on My books, then clear it and check it's gone from both.

**Acceptance Criteria**:

- **AC-01**: **Given** a member's entry page, **When** they choose a rating from 1 to 5 and
  save, **Then** the entry has that rating. The field is labelled "Rating (optional)" and
  offers "No rating" and the numbers 1 to 5, each with words ("1 – Didn't like it",
  "2 – It was OK", "3 – Liked it", "4 – Really liked it", "5 – Loved it").
- **AC-02**: **Given** an entry with a rating, **When** the member chooses "No rating" and
  saves, **Then** the entry has no rating.
- **AC-03**: **Given** Add a book (including Save and add another, spec 004, and the
  anthology section, spec 013), **When** the member chooses a rating, **Then** the new entry
  is saved with it. With no choice, it's saved with no rating.
- **AC-04**: **Given** a rating that isn't "No rating" or 1–5 (a tampered form), **When** the
  form is saved, **Then** nothing is saved, the field says "Choose a rating from 1 to 5, or
  No rating", and everything typed is kept.
- **AC-05**: **Given** any status (Want to read, Reading or Finished), **Then** the member may
  rate the entry. Changing the status keeps the rating.

---

### User Story 2 - See my ratings (Priority: P1)

The member scans My books and sees at a glance which books they rated highly.

**Why this priority**: a rating that's only visible on the entry page is little use.

**Independent Test**: with three entries rated 5, 2 and none, check My books and the book
pages.

**Acceptance Criteria**:

- **AC-06**: **Given** a rated entry, **When** My books lists it, **Then** its row shows the
  rating as text, for example "Rated 4 out of 5". An entry with no rating shows nothing for
  it. The rating is never shown by symbols or colour alone.
- **AC-07**: **Given** a rated entry, **When** the member opens the book's page (spec 016),
  **Then** it shows "Rated 4 out of 5" next to their status. The book page shows only the
  viewer's own rating. (On the entry page, the Rating field itself shows the rating,
  AC-01.)

---

### User Story 3 - Sort and filter by rating (Priority: P2)

The member wants their favourite books first, or the books they haven't rated yet.

**Acceptance Criteria**:

- **AC-08**: **Given** My books, **When** the member sorts by "Highest rated", **Then**
  entries are listed from 5 down to 1, with unrated entries last, and by title within the
  same rating. "Lowest rated" lists 1 up to 5, again with unrated entries last.
- **AC-09**: **Given** My books' filters, **When** the member chooses a rating filter,
  **Then** the list shows only matching entries. The choices are "Any rating" (the
  default), "5", "4 and up", "3 and up", "2 and up", "Rated" and "Not rated".
- **AC-10**: **Given** a rating filter or sort, **Then** it combines with search, the other
  filters and paging as they do today, is kept in the page's address, and works with
  JavaScript off. "Clear" (spec 018) clears the rating filter too.

---

### User Story 4 - The JSON API, privacy, access and speed (Priority: P2)

**Acceptance Criteria**:

- **AC-11**: **Given** the JSON API, **When** a client creates, updates or reads the member's
  own entries, **Then** `rating` is accepted (1–5 or null) and returned (a number or null).
  A value outside 1–5 is refused with 422. Leaving `rating` out of an update keeps it; null
  clears it. The list endpoint sorts by rating like My books, and filters with
  `min_rating` (1–5) and `rated` (true or false) (contracts/api-rating.md). The published
  contract says so.
- **AC-12**: **Given** another member's entry, **When** a member asks for it by page or API,
  **Then** they get 404, as today (Principle I). No page or API response shows one member's
  rating to another: not the book page, a series page, an author page, the catalog,
  Upcoming or suggestions.
- **AC-13**: **Given** the existing entries, **When** the change is applied, **Then** every
  entry has no rating and is otherwise unchanged. The change can be undone, which removes
  the ratings.
- **AC-14**: **Given** the entry page, Add a book and My books with ratings, sort and filter,
  **When** they're checked at the spec 003 widths, **Then** there's no sideways scroll,
  every control is at least 44 × 44 CSS px, axe reports no WCAG 2.2 AA violations, and
  everything works with JavaScript off.
- **AC-15**: **Given** 5,000 entries, **When** My books is sorted by rating or filtered by
  rating, **Then** it shows within the 1 s budget (p95).

### Edge Cases

- **Removing a book from my list:** the rating goes with the entry. Adding the book again
  starts with no rating, as the old status and notes aren't restored (spec 001).
- **Import (spec 002) and the quick-add rows (spec 015):** they add entries with no rating.
  The member can rate them afterwards.
- **Reading again** (times read, spec 001): the entry keeps one rating, whatever the times
  read. A member who changes their mind changes the rating.
- **Another member's rating:** never shown, even when both have the same book. There's no
  family average.

### Out of scope

- Half ratings, or a scale other than 1 to 5.
- Ratings of individual stories in a collection (stories have no status of their own,
  spec 009).
- A family or average rating, or ratings shared with other members.
- Rating from the quick-add rows on series and author pages (spec 015).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A member MUST be able to give each of their entries a rating from 1 to 5, or
  none, from the entry page and Add a book (AC-01–AC-05).
- **FR-002**: The rating MUST be shown as text wherever the member's own entry is shown on
  My books and the book page (AC-06, AC-07).
- **FR-003**: My books MUST sort and filter by rating (AC-08–AC-10).
- **FR-004**: The JSON API MUST accept and return the rating, and sort and filter by it
  (AC-11).
- **FR-005**: A rating MUST be private to the member who owns the entry (AC-12).
- **FR-006**: The change MUST keep existing data and be reversible (AC-13), and meet the
  accessibility, layout and speed budgets (AC-14, AC-15).

### Key Entities

- **Reading entry** (personal): gains an optional rating, a whole number from 1 to 5.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| A rating on an entry | Personal | Owner only | Owner only |

- **Duplication check**: none. The rating is stored only on the member's entry; no catalog
  record gets a rating or a copy of one.
- **Cross-user access**: none. Ratings are read only from the viewer's own entries (AC-12).

## AI Involvement *(mandatory)*

- **Generated content**: none.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: a rating from 1 to 5 on the member's own entries, only when
  the member chooses one.
- **Sent to external services**: none.

## API Changes

- **Changed schemas**: the reading entry create, update and read schemas gain an optional,
  nullable `rating` (integer, 1–5).
- **Changed endpoints**: the list of my entries gains the rating sort orders and a rating
  filter.
- **Breaking changes**: none. Every new field and parameter is optional, and existing
  responses only gain a field.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A member can rate, re-rate or clear a rating in one save on the entry page.
- **SC-002**: No other member can see a member's rating anywhere (checked for every page and
  endpoint that shows entries or books).
- **SC-003**: My books sorted or filtered by rating shows within 1 s (p95) at 5,000 books.
- **SC-004**: Every existing entry is unchanged after the change, apart from having no
  rating.

## Assumptions

- **Words with the numbers**: each rating has a short description (AC-01), so the scale
  means the same to everyone in the family and is clear to screen readers.
- **Rating is optional everywhere**; nothing asks the member to rate a book.
