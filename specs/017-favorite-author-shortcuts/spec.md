# Feature Specification: Favorite Author Shortcuts

**Feature Branch**: `017-favorite-author-shortcuts`

**Created**: 2026-11-25

**Status**: Draft

**Input**: User description: "Make marking a favorite author easier to find (bead books-2l7,
from the 2026-11-25 UI review)."

Today a member can mark an author as a favorite (spec 011) only on that author's page. Nothing
on the book or entry pages hints that favorites exist. The empty My favorite authors page
says only "Open an author's page and choose Add to my favorite authors", with nowhere to go.

Decisions made with the user on 2026-11-25:
- **Star toggles:** a one-tap star next to each author name on the book page (spec 016)
  byline and in my entry page's "More" section. They are not added to list rows.
- **Offer after finishing:** when a member finishes a book, the app offers to add its
  author to their favorites only if this is at least the second book by that author they
  have finished. It never offers an author who is already a favorite.

## Clarifications

### Session 2026-11-25

- Q: After the offer shows on the page a finishing save leads to, should reloading that same
  address show it again? → A: Yes, it may. The offer comes with the address the save leads
  to, like the app's other notices, and is checked again each time it shows, so it never
  offers an author who has become a favorite. Opening the page any other way never shows
  it.

## Overview

This feature adds three ways to reach favorites, all built on the spec 011 favorites:
- a star toggle by each author's name on the book page and on my entry page;
- a way forward from the empty My favorite authors page;
- an offer to add an author after finishing a second book by them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Star an author where I'm looking at their book (Priority: P1)

On the book page for *Small Gods*, a member sees "By Terry Pratchett ☆". They tap the star.
The page reloads with "Added Terry Pratchett to your favorite authors." and a filled star.
Tapping it again removes the favorite.

**Why this priority**: it puts the control where members already are, so it does the most
to make favorites findable.

**Independent Test**: on a book page and an entry page for a book with two authors, add
one author to favorites with the star, check the notice and both stars, then remove it.

**Acceptance Criteria**:

- **AC-01**: **Given** a book page (spec 016), **When** it shows, **Then** each author in the
  byline is followed by a star button. It's an empty star ☆ when the author isn't one of my
  favorites and a filled star ★ when they are. The author name still links to the author
  page.
- **AC-02**: **Given** my entry page, **When** it shows, **Then** each "All books by <author>"
  line in "More" has the same star button after the author's name.
- **AC-03**: **Given** a star button for an author who isn't my favorite, **When** I choose
  it, **Then** the author becomes one of my favorite authors, I return to the same page
  (at the same place), and a notice says "Added <author> to your favorite authors." The
  star is now filled. Choosing a filled star removes the favorite, with "Removed <author>
  from your favorite authors."
- **AC-04**: **Given** a star button, **Then** its accessible name says what it does and to
  whom: "Add <author> to my favorite authors" or "Remove <author> from my favorite
  authors". The star character is decorative. The button works without JavaScript.
- **AC-05**: **Given** a favorite change posted with a return address, **When** it
  redirects, **Then** it goes back only to an accepted page: a book page, my own entry
  page, the author page, or a page the offer (AC-12) shows on: My books, a series page or
  Add another. Any other address (another site, another page of this app, or an entry
  that isn't mine or doesn't exist) goes to the author page instead, as today. A book or
  series page that no longer exists is followed like any stale link. An unknown author
  returns Not Found, as today (spec 011 AC-09).

---

### User Story 2 - A way forward from no favorites (Priority: P2)

A new member opens My favorite authors and has none. The page tells them how to add one
and links to the Catalog to find a book.

**Why this priority**: it's small, and it turns a dead end into a starting point.

**Independent Test**: as a member with no favorites, open My favorite authors and follow
its link to the Catalog.

**Acceptance Criteria**:

- **AC-06**: **Given** I have no favorite authors, **When** I open My favorite authors,
  **Then** it says I haven't chosen any yet, explains that the star next to an author's
  name on a book page (or **Add to my favorite authors** on an author page) adds one, and
  links to the Catalog ("Browse the Catalog"). With one or more favorites, the page is
  unchanged.

---

### User Story 3 - Offer an author after a second finished book (Priority: P2)

A member marks *Small Gods* finished. They have already finished *Mort*, also by Terry
Pratchett, who isn't one of their favorites. The page they land on shows "You've finished
2 books by Terry Pratchett." with **Add Terry Pratchett to my favorite authors**. One tap
adds him. If they ignore it, nothing happens.

**Why this priority**: it catches the moment a member is most likely to want a favorite,
but each member only meets it now and then.

**Independent Test**: as a member who has finished one book by an author, finish a second
one by editing the entry, and check the offer shows and works. Then check it doesn't show
for a first finished book or for an author who is already a favorite.

**Acceptance Criteria**:

- **AC-07**: **Given** I save a book as finished that wasn't finished on my list before (by
  adding it with status Finished, or by changing my entry's status to Finished), **And**
  one of its authors isn't one of my favorites, **And** counting this book I have finished
  at least two different books by that author, **When** the page I land on shows, **Then**
  it shows an offer for that author: "You've finished <n> books by <author>." and an
  **Add <author> to my favorite authors** button.
- **AC-08**: **Given** the book has several authors who qualify, **Then** the offer names
  each one with its own button. Authors who don't qualify are not mentioned.
- **AC-09**: **Given** any of these, **Then** no offer shows:
  - this is the first book by that author I've finished;
  - the author is already one of my favorites;
  - the save didn't make the book finished (it was already finished, or I chose another
    status);
  - I open the page later by any other way than the address the save led to. (Reloading
    that address may show the offer again, checked afresh; see Clarifications.)

  Finishing the same book again (a re-read, spec 001) counts as one book, not two.
- **AC-10**: **Given** the offer, **When** I choose **Add <author> to my favorite
  authors**, **Then** the author becomes my favorite and I return to the page I was on,
  with "Added <author> to your favorite authors." and no offer for that author.
- **AC-11**: **Given** I ignore the offer, **Then** nothing is stored. The next time I
  finish another book by that author, the offer shows again.
- **AC-12**: **Given** the offer, **Then** it shows on whichever page the save leads to:
  my entry page after saving it; My books, a series page, or Add another after adding a
  book. A bulk import (spec 002) never shows an offer.

---

### User Story 4 - Private, accessible and fast (Priority: P2)

**Acceptance Criteria**:

- **AC-13**: **Given** another member has favorites and finished books, **Then** they never
  change what I see: my stars and offers use only my own favorites and my own finished
  entries (Principle I). Another member's favorite never shows as a filled star on my
  pages.
- **AC-14**: **Given** the book page and my entry page with star buttons, the empty My
  favorite authors page, and a page showing the offer, **When** they're checked at phone,
  tablet and laptop widths (spec 003), **Then**:
  - there is no sideways scroll;
  - every star and offer button is at least 44 × 44 CSS px;
  - axe reports no WCAG 2.2 AA violations;
  - a keyboard user reaches each star right after its author's name.
- **AC-15**: **Given** a catalog of 5,000 books, **When** the book page and my entry page
  show, and when a finish is saved, **Then** they stay within the 1 s budget (p95).

### Edge Cases

- **An author removed from the book between page load and the star tap:** the favorite
  still changes (it's about the author, not the book), and I return to the book page.
- **An author deleted meanwhile:** the star returns Not Found, as the author page's
  button does today.
- **A pen name:** the star favorites the name shown (the pen name), as the author page
  does. "Pen name of …" text stays as it is.
- **A story's author:** the count is of finished books, not stories (spec 009). Stories in
  a finished collection don't count separately.
- **Another member's entry id in a return address:** treated as any other refused address
  (AC-05); it never reveals whether that entry exists.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The book page and my entry page MUST show a star button after each author's
  name that adds or removes that author as my favorite in one tap (AC-01–AC-04).
- **FR-002**: The favorite change MUST return to the page it came from when that page is
  accepted (a book page, my own entry, the author page, or a page the offer shows on) and
  to the author page otherwise
  (AC-05).
- **FR-003**: The empty My favorite authors page MUST explain how to add one and link to
  the Catalog (AC-06).
- **FR-004**: After a save that makes a book finished, the page I land on MUST offer each of
  its authors who isn't my favorite and whose books I've now finished at least twice
  (different books), and only then (AC-07–AC-12).
- **FR-005**: Stars and offers MUST use only the viewer's own favorites and finished
  entries (Principle I, AC-13).
- **FR-006**: The changes MUST meet WCAG 2.2 AA and the spec 003 layouts, and keep the
  5,000-book budgets (AC-14, AC-15).

### Key Entities

- No new entities. The feature reads and writes the spec 011 favorite authors, and reads
  my own reading entries to count finished books by an author.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Authors on a book | Catalog | All members | — (read-only here) |
| My favorite authors | Personal | Owner only | Owner only |
| My finished entries (for the count) | Personal | Owner only | — (read-only here) |

- **Duplication check**: none. Nothing is copied; the offer is worked out from my entries
  when it shows, and nothing records that it was shown or ignored.
- **Cross-user access**: none. Another member's favorites and entries are never read for
  stars or offers.

## AI Involvement *(mandatory)*

- **Generated content**: none.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: none. Favorites already exist (spec 011).
- **Sent to external services**: none.

## API Changes

- **New endpoints**: none. The JSON API already has `PUT` and `DELETE
  /api/v1/me/favorite-authors/{author_id}` (spec 011). The changes are to HTML pages only.
- **Breaking changes**: none.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a book page or my entry page, a member can add or remove an author as a
  favorite in one tap, without leaving the page.
- **SC-002**: A member with no favorites has a link onward from My favorite authors.
- **SC-003**: A member who finishes a second book by an author who isn't a favorite is
  offered that author on the page the save leads to, and on no other page.
- **SC-004**: The book page, my entry page and saving a finish stay within 1 s (p95) at
  5,000 books.

## Assumptions

- **The author page's button is unchanged** (spec 011 AC-08) and still returns to the
  author page.
- **No "don't ask again"**: ignoring the offer stores nothing. It shows only on the page a
  finishing save leads to (and on a reload of that address), so it can't nag between
  finishes.
- **Books finished before this feature, or by an import, count** towards the two finished
  books. Only showing the offer is limited to a member's own finishing save.
- **List rows get no stars**: My books, Catalog, Upcoming and series rows stay as they are,
  to keep rows simple and touch targets clear on phones.
- **"Finished" means the Finished status** (spec 001). Reading and Want to read don't count.
