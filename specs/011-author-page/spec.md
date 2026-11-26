# Feature Specification: Author Page and Favorite Authors

**Feature Branch**: `011-author-page`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "Author page, with personal extras such as marking a favorite
author" (bead books-e8w). Today an author is reachable only through Edit author. Add an
Author page with:
- the author's details;
- all their catalog books, grouped by series;
- which books are on the viewer's own list (with status), and **Add to my list** for the
  rest.

Also let a member mark an author as a **Favorite**, and filter My books by favorite authors.

## Clarifications

### Session 2026-11-22

- **Q: Which personal extras are in scope?** → Favorite only. A private note or rating per
  author can follow as its own bead.
- **Q: What happens when someone deletes an unused author (spec 008) that a member
  favorites?** → Deletion is blocked while any member favorites the author. The message
  doesn't say who. This reveals that *some* member favorites the author, which Principle I
  forbids. The maintainer chose to allow it, so the constitution is amended to 2.0.0 (a
  narrow Principle I exception) in the same pull request.
- **Q: Where are favorites used beyond the Author page?** → A My favorite authors list, and
  a My books filter.

## Overview

An **Author page** (`/authors/{id}`) shows one author as the family catalog knows them:
- their name, and their real name if they write under a pen name;
- every catalog book that lists them, grouped by series;
- the stories that list them (spec 009).

For each book, the viewer sees their **own** status, or **Add to my list**.

A member can mark an author as one of **my favorite authors**. A favorite is personal: only
that member sees it. Favorites appear on the author's page, on a **My favorite authors**
page, and as a My books filter.

### Example

Alice opens Jim Butcher's page:

| Section | Shows |
|---|---|
| Heading | **Jim Butcher** · ★ One of your favorite authors · **Remove from my favorite authors** · Edit author |
| The Dresden Files | #1 Storm Front · Finished · On my list |
| | #2 Fool Moon · **Add to my list** |
| | #18 Twenty Lives · Coming 3 Mar 2027 · **Add to my list** |
| Other books | Side Jobs · Want to read · On my list |
| Stories | #1.5 The Dresden Files — Restoration of Faith · in Side Jobs |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See an author's books (Priority: P1)

From a book anywhere in the app, a member opens its author's page. There they see every
catalog book by that author, in series order, and can tell which are on their own list.

**Why this priority**: the page is the reason for the feature; favorites build on it.

**Independent Test**: open Jim Butcher from a My books row; check the series groups, the
order, your own statuses, Add to my list for the others, and that another member's entries
never show.

**Acceptance Criteria**:

- **AC-01**: **Given** a book row on My books, the Catalog, Upcoming or a series page,
  **Then** each author's name links to that author's page. **Given** an entry page or Edit
  book, **Then** each author is listed with a link to their page, as well as the existing
  **Edit author** link.
- **AC-02**: **Given** an author, **When** a member opens their page, **Then** it shows:
  - the name as a heading;
  - "Pen name of <real name>" when it is a pen name with a real name, or "Pen name" when it
    has none;
  - an **Edit author** link to Edit author.

  An unknown author id returns 404. A signed-out visitor is sent to sign in.
- **AC-03**: **Given** the author's catalog books, **Then** the page groups them:
  - one group per series, by series name (A–Z, ignoring case);
  - each group headed by the series name, linking to the series page;
  - books in a group by number (unnumbered last), then title;
  - then **Other books** (not in a series), by title.

  Each row shows the title (linking to Edit book), the number when it has one, and "Coming
  <date>" while the book isn't out.
- **AC-04**: **Given** a listed book, **Then**:
  - on the viewer's list: its row shows the viewer's status ("Finished", "Reading" or
    "Want to read") and an **On my list** link to the viewer's entry;
  - otherwise: an **Add to my list** link (Add a book started from that book, spec 006),
    whose accessible name includes the title.
- **AC-05**: **Given** another member has one of the author's books on their list, **Then**
  the viewer's page row for that book is the same as when no member has it (Principle I).
- **AC-06**: **Given** stories that list the author (spec 009), **Then** a **Stories**
  section lists each as "#n Series — Title" with "in <book>" links to the books it is in.
  Without stories there is no section.
- **AC-07**: **Given** an author no book lists, **Then** the page says "No book in the
  family catalog lists this author."

---

### User Story 2 - Mark a favorite author (Priority: P1)

On an author's page, a member adds the author to their favorite authors, or removes them.
Only they see it.

**Why this priority**: it is the personal extra the request is for.

**Independent Test**: as Alice, add Jim Butcher to favorites and see it shown; as Ben, see
that Jim Butcher isn't marked; remove it as Alice.

**Acceptance Criteria**:

- **AC-08**: **Given** an author who isn't one of the viewer's favorites, **When** the
  viewer chooses **Add to my favorite authors**, **Then** the page reloads and shows:
  - "Added to your favorite authors.";
  - "★ One of your favorite authors" (the star is decorative; the text says it);
  - **Remove from my favorite authors**.

  Removing reverses this, with "Removed from your favorite authors."
- **AC-09**: **Given** Alice favorites an author, **Then**:
  - Ben's page for that author shows it as not a favorite, and none of his lists include it;
  - adding a favorite that is already one changes nothing;
  - removing one that isn't changes nothing;
  - a favorite for an unknown author returns 404;
  - a request without the session's CSRF token is refused (403).
- **AC-10**: **Given** the JSON API, **Then**:
  - `GET /api/v1/me/favorite-authors` lists the caller's favorite authors by sort name;
  - `PUT /api/v1/me/favorite-authors/{author_id}` adds one (204, idempotent);
  - `DELETE /api/v1/me/favorite-authors/{author_id}` removes one (204, idempotent);
  - an unknown author returns 404;
  - every response contains the caller's favorites only.
- **AC-11**: **Given** the database, **Then**:
  - a member can hold an author as a favorite at most once (a constraint);
  - deleting a member's account removes their favorites;
  - a favorited author can't be deleted at the database level;
  - the change can be undone by a reversible migration.

---

### User Story 3 - Use my favorites (Priority: P2)

A member sees all their favorite authors in one place, and can narrow My books to books by
them.

**Why this priority**: favorites are more useful once they lead somewhere.

**Independent Test**: favorite two authors; open My favorite authors; on My books choose
"My favorite authors" in the Author filter.

**Acceptance Criteria**:

- **AC-12**: **Given** the viewer's favorites, **When** they open **My favorite authors**
  (`/authors/favorites`), **Then** it lists them by sort name, each linking to the author's
  page. It is linked from My books and from every author page. With none, it says "You
  haven't chosen any favorite authors yet." and explains how to choose one.
  *Replaced 2026-11-26 by [spec 018](../018-navigation-model/spec.md) (AC-02–AC-07): the Authors page with **Favorites only**.
  `/authors/favorites` redirects there.*
- **AC-13**: **Given** My books, **Then** the Author filter offers **My favorite authors**
  (after **Any author**). Choosing it lists the viewer's books that have at least one
  favorite author, and the choice is kept across sorting and paging. The JSON API's list of
  the caller's readings takes `favorite_authors=true` for the same filter.

---

### User Story 4 - Favorites and deleting unused authors (Priority: P2)

Spec 008 lets any member delete an author no book lists. While a member keeps that author as
a favorite, the author stays.

**Why this priority**: it keeps a favorite from silently disappearing. It is a rule on an
existing action, not a new journey.

**Independent Test**: create an author with no books. Ben favorites them. Alice can't delete
them and isn't told who favorites them. Ben removes the favorite, and Alice can delete them.

**Acceptance Criteria**:

- **AC-14**: **Given** an author no book or story lists, who is one of the viewer's own
  favorites, **When** the viewer opens Edit author, **Then**:
  - instead of **Delete author**, it says "This author is one of your favorite authors.
    Remove them from your favorites to delete them.";
  - it links to their page.
- **AC-15**: **Given** such an author favorited by another member only, **Then** Edit
  author says "A family member has this author as a favorite, so they can't be deleted."
  There is no **Delete author** button, and no name or count is shown (constitution 2.0.0,
  Principle I exception). The author is left out of **Authors with no books** and its
  count.
- **AC-16**: **Given** a member favorites an author between another member's delete
  confirmation and the delete, **Then** the author isn't deleted, and Edit author shows the
  AC-14 or AC-15 message. `DELETE /api/v1/authors/{id}` returns 409 with code
  `author_is_favorite`.
- **AC-17**: **Given** an author deleted while a member's page for them is open, **When**
  that member adds them to favorites, **Then** they get 404, and nothing is stored.

---

### User Story 5 - Accessible on every device (Priority: P2)

**Acceptance Criteria**:

- **AC-18**: **Given** the Author page and My favorite authors, **Then**:
  - both work without JavaScript;
  - automated checks find no WCAG 2.2 AA violations at phone, tablet and laptop widths;
  - nothing scrolls sideways;
  - every button and navigation link is at least 44 px;
  - the favorite button can be used by keyboard alone.

### Edge Cases

- **An author with many books** (300 in the performance seed): the page still meets its
  budget (SC-001).
- **A book with several authors**: it is listed on each author's page, and each name links
  to its own page.
- **Another member's records**: favorites are read and changed only for the session user.
  Another member's favorites can't be requested at all, because there is no path that names
  a member. The one thing revealed is "some member favorites this author", when deletion is
  refused (AC-15).
- **Pen names**: the page shows the real name as text. Linking pen names to a real-name
  author is out of scope; the catalog has no such link.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an Author page for every catalog author, reachable
  from book rows, entry pages and Edit book (AC-01 – AC-02).
- **FR-002**: The page MUST list the author's books grouped by series, and their stories,
  with the viewer's own status or **Add to my list** (AC-03 – AC-07).
- **FR-003**: A member MUST be able to add and remove an author from their own favorites,
  from the page and the JSON API (AC-08 – AC-10).
- **FR-004**: Favorites MUST be personal data, kept per member, enforced by the database
  (AC-11). They MUST NOT be shown to any other member, except the AC-15 refusal.
- **FR-005**: The system MUST offer My favorite authors and a My books favorites filter,
  with the same filter in the JSON API (AC-12 – AC-13).
- **FR-006**: An author a member favorites MUST NOT be deleted. The refusal MUST NOT
  identify the member (AC-14 – AC-17).
- **FR-007**: The pages MUST work without JavaScript, meet WCAG 2.2 AA and follow the
  spec 003 layouts (AC-18).

### Key Entities

- **Favorite author** (new, personal): a member and an author, with when it was added. A
  member holds a given author at most once.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Author name, real name, books, stories | Catalog | All members | Not written here (Edit author is unchanged) |
| My entries' statuses on the Author page | Personal | Owner only | Not written here |
| Favorite author | Personal | Owner only; the AC-15 refusal shows only that *some* member has one | Owner only |

- **Duplication check**: a favorite stores only the member and the author ids, with a
  timestamp. No catalog data is copied.
- **Cross-user access**: none, except the amended Principle I exception. Deleting an unused
  author is refused while any member favorites them, without naming who (constitution
  2.0.0, ratified with this spec).

## AI Involvement *(mandatory)*

- **Generated content**: None.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: which authors a member marks as favorites, with the time.
  This is the minimum the feature needs.
- **Sent to external services**: None.

## API Changes

- **New endpoints**:
  - `GET /api/v1/me/favorite-authors`;
  - `PUT /api/v1/me/favorite-authors/{author_id}`;
  - `DELETE /api/v1/me/favorite-authors/{author_id}`.
- **Changed**:
  - `GET /api/v1/me/readings` gains an optional `favorite_authors` boolean;
  - `DELETE /api/v1/authors/{id}` may return 409 with the new code `author_is_favorite`.
- **Breaking changes**: None. All changes are additions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With 5,000 catalog books, the Author page for an author with 300 books loads
  in under 1 second at p95. The same holds for My favorite authors and for the My books
  favorites filter.
- **SC-002**: From any book row, a member reaches its author's full list of books in one
  step.
- **SC-003**: Automated accessibility checks report no WCAG 2.2 AA violations on the new
  pages at phone, tablet and laptop widths.

## Assumptions

- **The address is `/authors/{id}`** (with `/authors/favorites`). Edit author stays at
  `/catalog/authors/{id}/edit`.
- **The title of a book row links to Edit book**, as on the Catalog page (spec 010). The
  status and **On my list** link lead to the viewer's own entry.
- **Favorites have no order or note**: they are listed by sort name.
- **The Catalog page gets no favorites filter** in this feature.
- **The unused-authors list** (spec 008) leaves out favorited authors, because they can't be
  deleted while favorited.
