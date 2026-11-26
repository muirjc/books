# Feature Specification: Consistent Navigation

**Feature Branch**: `018-navigation-model`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "Why not have an Author option on the main top menu? Why have
the Upcoming option on the My books page and have it on the top menu? Consistency seems to
be lacking in how the pages are designed." (bead books-637, with the UI agent's review)

Today the top menu is My books, Add a book, Catalog, Upcoming and Import (plus Accounts for
Admins). It mixes places, an action and a tool:
- **Authors and series** have full pages but no way in, other than one of their books.
- **Upcoming** is both a menu page and an "Upcoming only" checkbox on My books, and the two
  show different things.
- **Favorite authors** have three ways in: a link under the My books filters, a choice in
  the Author filter, and their own page.
- **Now out** is a box on My books that nothing else points to.

Decisions made with the user on 2026-11-26:
- **Principle:** the menu lists places, filters narrow a place, and actions don't take
  menu places.
- **Authors** gets a menu item and an Authors page. It replaces the My favorite authors
  page.
- **Upcoming** stays a menu page only. The "Upcoming only" checkbox on My books goes.
- **Series** gets no menu item. The Catalog gets a Series view.
- **Now out** moves to the top of the Upcoming page, with a one-line pointer on My books.

## Clarifications

### Session 2026-11-26

- Q: "Add a book" is both in the menu and a button at the top of My books, Catalog and
  Upcoming. Which should stay? → A: Both. The menu keeps it in the separate action group
  (with Import), and the page buttons stay. It's the most-used action, and the group
  shows it's an action, not a place.

## Overview

After this feature:
- **The menu** reads My books · Catalog · Authors · Upcoming, then Add a book and Import
  as a separate group (and Accounts for Admins).
- **Each kind of thing has one front door:** my books, catalog books, authors, series
  (through the Catalog) and upcoming books.
- **Filters only narrow** the page they're on.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find any author (Priority: P1)

A member wants to see Terry Pratchett's books. They choose **Authors** in the menu, type
"prat", and open his page. Another time they choose **Favorites only** to see the authors
they follow.

**Why this priority**: it's the user's first question and the biggest gap. Authors have
had pages since spec 011 but no way to find one.

**Independent Test**: open Authors from the menu, search, filter to favorites, star an
author from the list, and open an author's page.

**Acceptance Criteria**:

- **AC-01**: **Given** any signed-in page, **When** it shows, **Then** the menu reads, in
  this order, My books · Catalog · Authors · Upcoming, then Add a book and Import as a
  visually separate group (and Accounts for Admins). The current place is marked
  (`aria-current="page"`). Author pages and the Authors page mark **Authors**. The Catalog,
  the Series view, series pages and book pages mark **Catalog**.
- **AC-02**: **Given** the Authors page (`/authors`), **When** it shows, **Then**:
  - it lists every catalog author, my favorites first, then everyone else, each group by
    sort name;
  - each row shows the author's name, linking to the author page, with "pen name of …"
    when set;
  - each row shows how many catalog books list the author, and how many of those I've
    finished ("3 books · 2 read");
  - each row has the spec 017 star button for that author.
- **AC-03**: **Given** the Authors page, **When** I search, **Then** it lists only authors
  whose name, sort name or real name contains the text (ignoring case, as on the
  Catalog). With JavaScript the list updates as I type, as on the Catalog; without it,
  the form submits.
- **AC-04**: **Given** the Authors page, **When** I choose **Favorites only**, **Then** it
  lists only my favorite authors. With JavaScript the list updates when the box changes,
  as the Catalog's "Not on my list" does; without it, **Apply** submits. With no favorites, it shows the spec 017 empty-favorites
  text (how to add one, with **Browse the Catalog**).
- **AC-05**: **Given** a star on the Authors page, **When** I choose it, **Then** the
  favorite changes and I return to the Authors page with the same search, filter and page,
  with the spec 017 notice.
- **AC-06**: **Given** more than 50 matching authors, **Then** the page shows 50 at a time
  with Previous and Next, keeping the search and filter.
- **AC-07**: **Given** the old address `/authors/favorites`, **When** it's requested,
  **Then** it redirects to the Authors page with **Favorites only** chosen. Links that
  pointed to it now point to the Authors page with Favorites only.
- **AC-08**: **Given** authors that no book lists (spec 008), **Then** the "Authors with no
  books (n)" link moves from My books to the Authors page, unchanged otherwise.

---

### User Story 2 - One place for what's coming and what's new (Priority: P1)

A member wants to know what's coming out and what has just come out. They choose
**Upcoming**: "Now out" sits at the top, then "On my list", then "Also coming in the family
catalog".

**Why this priority**: it's the user's second question. The same idea in two places with
different contents is the inconsistency they noticed.

**Independent Test**: with a book of mine out last week, one of mine coming next month and
a catalog book coming, check Upcoming shows all three in their sections. Check My books has
no Upcoming checkbox and shows the Now out pointer.

**Acceptance Criteria**:

- **AC-09**: **Given** My books, **When** it shows, **Then** there is no "Upcoming only"
  checkbox and no "My favorite authors" link under the filters. The Author filter's "My
  favorite authors" choice stays.
- **AC-10**: **Given** an old address with `upcoming=1` on My books, **When** it's
  requested, **Then** it redirects to the Upcoming page.
- **AC-11**: **Given** books on my list I want to read that came out in the last 30 days
  (spec 007), **When** I open Upcoming, **Then** a "Now out" section comes first, listing
  them as the box on My books does today. Otherwise that section isn't shown.
- **AC-12**: **Given** such books, **When** I open My books, **Then** instead of the box,
  one line says "1 book you want to read is now out" or "<n> books you want to read are
  now out", linking to the Now out section of Upcoming. With none, nothing shows.
- **AC-13**: **Given** the Upcoming page, **Then** its sections are, in order: "Now out"
  (when there are any), "On my list" and "Also coming in the family catalog", as today.

---

### User Story 3 - Browse series from the Catalog (Priority: P2)

A member wants to see which series the family has. On the Catalog they switch from
**Books** to **Series**, and see each series with how many books it has and how many
they've finished.

**Why this priority**: series are usually reached from a book, so this matters less than
authors. It still gives them a front door without a menu item.

**Independent Test**: on the Catalog, switch to Series, search for one, and open its
series page.

**Acceptance Criteria**:

- **AC-14**: **Given** the Catalog, **When** it shows, **Then** a "Books | Series" switch
  sits under the heading. Books is the Catalog as today. Each choice is a link, and the
  current one is marked.
- **AC-15**: **Given** the Series view, **When** it shows, **Then** it lists every series
  by name. Each row shows the name, linking to the series page, how many catalog books are
  in it, and how many of those I've finished ("12 books · 4 read").
- **AC-16**: **Given** the Series view, **When** I search, **Then** it lists only series
  whose name contains the text, as on the Authors page. More than 50 show 50 at a time.

---

### User Story 4 - Private, accessible and fast (Priority: P2)

**Acceptance Criteria**:

- **AC-17**: **Given** another member's favorites and finished books, **Then** they never
  change what I see: the star, "N read" counts and favorites-first order on the Authors
  page, "N read" in the Series view, and Now out use only my own data (Principle I).
- **AC-18**: **Given** the menu, the Authors page (with results, a search with none, and
  Favorites only empty), the Series view, Upcoming with all three sections, and My books
  with the Now out line, **When** they're checked at the spec 003 widths, **Then**:
  - there's no sideways scroll;
  - every link and button is at least 44 × 44 CSS px;
  - axe reports no WCAG 2.2 AA violations;
  - the menu fits on at most two rows on a 360 px phone, for a member and for an Admin.
- **AC-19**: **Given** 5,000 books and 1,500 authors, **When** the Authors page (first
  page, a search, Favorites only) and the Series view show, **Then** they stay within the
  1 s budget (p95). My books, Upcoming and the Catalog keep their budgets.

### Edge Cases

- **An author with no books:** they're listed with "0 books" (AC-02), and also appear
  under "Authors with no books".
- **A pen name and the real author both in the catalog:** they're separate rows, as on
  their pages.
- **A search with no matches:** "No authors match “…”." (or series), with a link to clear
  the search.
- **Unfavoriting on the Authors page with Favorites only on:** I return to the filtered
  list, where that author is no longer listed. The notice still names them.
- **A series with only stories (spec 009) and no books:** it's listed with "0 books".

### Amended specs

This feature replaces behaviour required by earlier specs. Their acceptance criteria are
marked "Amended" or "Replaced" with today's date:
- spec 003: AC-08 (found during implementation: at 1,024 px the header no longer fits one
  row, so the account actions wrap; decided with the user 2026-11-26);
- spec 007: AC-10, AC-11, AC-14, AC-19, AC-20, AC-21, FR-004 and SC-002;
- spec 008: AC-01 (the link moves to the Authors page);
- spec 011: AC-12;
- spec 017: AC-06.

Tests of what those criteria still require keep their tags. These are:
- spec 007 AC-10's JSON API filter;
- spec 007 AC-14 to AC-18's Now out rules, which now apply on Upcoming;
- spec 017 AC-06's empty text.

Tests of removed behaviour are rewritten to this spec's criteria and tagged `018/AC-xx`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The menu MUST list places in the order My books, Catalog, Authors,
  Upcoming, with Add a book and Import as a separate group, and mark the current place
  (AC-01).
- **FR-002**: An Authors page MUST list every author with search, Favorites only,
  favorites first, counts, a star and pages of 50. It replaces the My favorite authors
  page (AC-02–AC-08).
- **FR-003**: Upcoming MUST be the only place for upcoming and newly-out books. My books
  loses its Upcoming checkbox and Now out box, and gains a one-line pointer (AC-09–AC-13).
- **FR-004**: The Catalog MUST offer a Series view with search, counts and pages of 50
  (AC-14–AC-16).
- **FR-005**: Personal data on these pages MUST be the viewer's own (Principle I, AC-17).
- **FR-006**: The changes MUST meet WCAG 2.2 AA and the spec 003 layouts, and keep the
  5,000-book budgets (AC-18, AC-19).

### Key Entities

- No new entities. The pages read catalog authors, series and books, plus my own
  favorites and reading entries.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Authors, series, book counts | Catalog | All members | — (read-only here) |
| My favorites, my "read" counts, Now out | Personal | Owner only | Favorites: owner only (the star) |

- **Duplication check**: none. Counts are worked out when a page shows.
- **Cross-user access**: none. Another member's favorites and entries are never read.

## AI Involvement *(mandatory)*

- **Generated content**: none.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: none.
- **Sent to external services**: none.

## API Changes

- **New endpoints**: none. These are HTML pages. The JSON API keeps
  `GET /api/v1/me/favorite-authors`.
- **Breaking changes**: none.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A member can reach any author's page in at most three steps from any page
  (menu, search, choose), without first finding one of their books.
- **SC-002**: Upcoming and newly-out books appear in exactly one place, and favorites in
  one list.
- **SC-003**: Every item in the menu's main group is a place, and none duplicates a
  filter. Actions (Add a book, Import) sit in their own group.
- **SC-004**: The Authors page and Series view show within 1 s (p95) at 5,000 books and
  1,500 authors.

## Assumptions

- **Add a book and Import stay in the menu**, as a separate action group, and the "Add a
  book" buttons on My books, Catalog and Upcoming stay too (Clarifications). The menu's
  places come first, so the group reads as actions.
- **"Read" means Finished** (spec 001). Reading and Want to read don't count.
- **Counts are of books, not stories** (spec 009).
- **The "Authors with no books" page** (spec 008) keeps its address and rules. Only its
  link moves.
- **The spec 007 "Upcoming only" sort** (soonest first) lives on in the Upcoming page's
  "On my list" section, which is already soonest first.
