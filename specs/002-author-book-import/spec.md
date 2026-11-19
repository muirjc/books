# Feature Specification: Import an Author's Books

**Feature Branch**: `002-author-book-import`

**Created**: 2026-11-19

**Status**: Draft

**Input**: User description: "Ability to import data from an approved website. The user
enters an author name; the app goes out and gets data about all books for that author. The
user then selects books for addition." (bead books-0tw)

<!--
  This template is a project override of the Spec Kit core template. It implements the
  spec requirements of .specify/memory/constitution.md ("Spec Kit flow", step 1).

  Every section marked *(mandatory)* MUST be completed. Automated tests are REQUIRED for
  every acceptance criterion (Constitution Principle V); this spec counts as an explicit
  request for test tasks.
-->

## Scope

Adding books one at a time (spec 001) is slow when a family reads many books by the same
author. This feature lets a member look an author up on an approved book-data website, see
that author's books, and add the ones they choose to their own reading list in one step.
Books new to the family go into the shared catalog at the same time, because every list
entry points at a catalog book (Constitution Principle II).

This is the first feature that calls an external book-data source. It introduces the source
adapter that the planned AI summary feature will reuse. The roadmap in spec 001 lists "002 –
AI Summary Drafts" and "003 – Covers and Ratings" as planned; those take the next free
numbers when they are specified.

Out of scope: importing from Goodreads or Kindle exports, importing by series or by title,
cover images (planned for the covers feature), summaries or descriptions from the source,
and automatic or scheduled re-imports.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find an author's books and add the ones I choose (Priority: P1)

A member types an author's name, for example "Brandon Sanderson". The app asks the
approved book-data sites for that author and shows their books as a list: title, first
published year, and series and number where the site gives them. Books already on the
member's list, and books already in the family catalog, are marked. The member ticks the
books they want, picks a status for them (Finished unless they change it) and confirms. The
ticked books go onto that member's list only; nothing is added before they confirm.

**Why this priority**: this is the whole feature. Without it there is nothing to import.

**Independent Test**: with the external sites replaced by recorded responses, a member
searches an author, ticks three of the books shown and confirms; exactly those three books
are on that member's list afterwards, the catalog holds one copy of each, and no other
member's list changed.

**Acceptance Criteria**:

- **AC-01**: **Given** a signed-in member, **When** they search for an author by name,
  **Then** they see that author's books from the switched-on sites, each with its title and,
  where the site provides them, first published year, series and number in series.
- **AC-02**: **Given** the list of an author's books, **When** the member ticks some books and
  confirms, **Then** exactly the ticked books are added to that member's own list with the
  chosen status, books new to the family are added to the catalog with that author, and a
  summary says how many were added.
- **AC-03**: **Given** the list of an author's books, **When** the member leaves without
  confirming, **Then** nothing is added to the catalog or to any list.
- **AC-04**: **Given** a book in the results that is already in the catalog, **When** the list
  is shown, **Then** that book is marked "In the family catalog", and confirming it adds it to
  the member's list without creating a second catalog copy.
- **AC-17**: **Given** a book in the results that is already on the member's list, **When** the
  list is shown, **Then** it is marked "Already on your list" and can't be ticked (spec 001
  FR-017).
- **AC-18**: **Given** Alice imports books, **When** Ben views his list, **Then** none of
  Alice's imported books appear on it, although Ben can find them in the catalog.
- **AC-19**: **Given** the confirm step, **When** the member leaves the status unchanged,
  **Then** the books are added as Finished; **and when** they choose Want to read or Reading,
  **Then** all the ticked books get that status.
- **AC-05**: **Given** an author whose name is already in the catalog (ignoring
  capitalization), **When** their books are imported, **Then** the existing author is used
  and no second author is created.
- **AC-06**: **Given** an imported book with co-authors, **When** it is added, **Then** all its
  authors are added in the site's order, reusing any author already in the catalog.
- **AC-07**: **Given** an imported book, **When** it is saved, **Then** the catalog records
  which site it came from, the site's identifier for it, who imported it and when.

---

### User Story 2 - Pick the right author when names are shared (Priority: P2)

Some names match more than one author on the site, or the member types only part of a
name. The app shows the matching authors, with enough detail to tell them apart (for
example birth and death years, a well-known title, the number of books), and the member
picks one before seeing books.

**Why this priority**: without it, common names give a mixed or wrong list. It is not
needed for the many authors whose names are unique.

**Independent Test**: with recorded responses for a name that matches three authors, the
member sees three choices, picks the second, and the book list shows only that author's
books.

**Acceptance Criteria**:

- **AC-08**: **Given** a name that matches more than one author on the site, **When** the
  member searches, **Then** they see each matching author with distinguishing details and
  choose one before any books are listed.
- **AC-09**: **Given** a name that matches no author on the site, **When** the member
  searches, **Then** they see "No author found" with a link to add a book by hand, and
  nothing changes.

---

### User Story 3 - Import a long bibliography without fuss (Priority: P3)

Prolific authors have hundreds of entries, including omnibus editions, translations and
duplicates. The member can narrow and sort the list, and select many books at once.

**Why this priority**: makes the feature practical for big names; the basic import already
works without it.

**Independent Test**: with recorded responses for an author with 300 entries, the member
filters to one series, selects all of it in one action, and confirms; only that series'
books are added.

**Acceptance Criteria**:

- **AC-10**: **Given** an author's book list, **When** the member sorts it by title or by first
  published year, or filters it by series or by text in the title, **Then** the list updates
  to match.
- **AC-11**: **Given** a filtered list, **When** the member chooses "Select all shown", **Then**
  every shown book that is not already in the catalog is ticked, and no hidden book is.
- **AC-12**: **Given** the site lists several entries for one work (editions or the same title
  twice), **When** the list is shown, **Then** each work appears once.

---

### User Story 4 - An Admin chooses which book sites are used (Priority: P2)

The app supports two approved book-data sites, Open Library and Google Books. An Admin
switches each one on or off on a settings screen. Searches use only the sites that are on.
With both on, the results are combined into one list.

**Why this priority**: the family decides which sites the app talks to. A working default
(Open Library on) means P1 works before an Admin ever opens the screen.

**Independent Test**: an Admin turns Google Books off and Open Library on; a member's search
contacts only Open Library. With both on, a book that both sites list appears once.

**Acceptance Criteria**:

- **AC-20**: **Given** a signed-in Admin, **When** they open the book-site settings, **Then**
  they see each approved site with an on/off switch and can save a change; **and given** a
  member without the Admin role, **When** they try to open or change these settings,
  **Then** it is refused.
- **AC-21**: **Given** only one site is switched on, **When** a member searches, **Then** only
  that site is contacted.
- **AC-22**: **Given** both sites are on, **When** a member loads an author's books, **Then**
  the results from both are combined, a book both sites list appears once, and each book
  shows which site it came from.
- **AC-23**: **Given** no Google Books key is configured on the server, **When** an Admin opens
  the settings, **Then** Google Books is shown as unavailable and can't be switched on.
- **AC-24**: **Given** every site is switched off, **When** a member opens the import screen,
  **Then** they see "Book import is turned off. Ask an Admin to switch on a book site," and
  can still add books by hand.
- **AC-25**: **Given** both sites are on and one of them fails, **When** a member loads an
  author's books, **Then** they see the other site's results with a note that one site
  couldn't be reached.

---

### Edge Cases

- **The site is slow, down or refusing requests.** The member sees a clear message that the
  site couldn't be reached and can try again later or add books by hand; nothing changes.
  *(AC-13)*
- **The site's series number clashes** with a book already at that number in the same
  catalog series. The book is still added, without the number, and the summary says which
  books need a number checked. *(AC-14)*
- **The site gives an ISBN that isn't a valid 13-digit ISBN** (for example a 10-digit one that
  can't be converted, or a malformed value). The book is added without an ISBN. *(AC-15)*
- **Two members import the same book at nearly the same time.** The catalog still holds one
  copy (spec 001 FR-011). *(AC-16)*
- **The author in the catalog is a pen name** and the member searches by the writer's real
  name. The site is searched with what the member typed; the existing catalog author is
  reused only when the site's author name matches it.
- **A selected book disappears from the site** between listing and confirming. The book is
  added from what was listed; nothing is fetched again at confirm time.
- **Personal records.** Imported books go onto the importing member's list only, taken from
  the session. Other members' lists are unchanged, and nothing shows them what is on the
  importer's list (Constitution Principle I). *(AC-18)*
- **A ticked book is already on the member's list** by the time they confirm (for example
  added in another tab). It is skipped and listed in the summary as already on the list.

- **AC-13**: **Given** the site times out or returns an error, **When** the member searches or
  loads an author's books, **Then** they see "The book site couldn't be reached. Try again
  later, or add the book by hand," and nothing is added.
- **AC-14**: **Given** an imported book whose series number is already used by another book in
  that catalog series, **When** it is added, **Then** it is saved in the series without a
  number, and the summary lists it as needing its number checked.
- **AC-15**: **Given** a site ISBN that is not a valid 13-digit ISBN and can't be converted to
  one, **When** the book is added, **Then** it is saved without an ISBN.
- **AC-16**: **Given** two members confirming the same new book at the same time, **When** both
  imports finish, **Then** the catalog holds that book once and both members see it as
  imported.

## Requirements *(mandatory)*

### Functional Requirements

**Searching**

- **FR-001**: Any signed-in member MUST be able to search the switched-on book-data sites for
  an author by name. The approved sites are Open Library and Google Books; no other site may
  be contacted.
- **FR-002**: When a name matches more than one author on the site, the system MUST list the
  matches with distinguishing details (such as birth and death years, a well-known title and
  the number of books) and let the member choose one.
- **FR-003**: For the chosen author, the system MUST list their books with title, and where
  the site provides them: first published year, co-authors, series, number in series and
  ISBN.
- **FR-004**: The list MUST show each work once, even when the site lists several editions.
- **FR-005**: The list MUST mark books already on the member's own list (which can't be
  selected) and books already in the catalog. A book counts as already in the catalog when it
  has the same ISBN as a catalog book, or the same site identifier, or the same title
  (ignoring capitalization, punctuation and a leading "The", "A" or "An") and the same first
  author. The same rule identifies one book listed by both sites.
- **FR-006**: The member MUST be able to sort the list by title or first published year,
  filter it by series or title text, and select all shown books at once.

**Importing**

- **FR-007**: Nothing MUST be written to the catalog until the member confirms their selection.
- **FR-008**: On confirmation, the system MUST add each selected book that is not already in the
  catalog, with its authors in the site's order, series and number in series where given.
  Existing authors and series MUST be reused (matching names ignoring capitalization), per
  spec 001 FR-011. It MUST then add every selected book to the importing member's own list.
- **FR-009**: Every imported book MUST record the source site, the site's identifier for the
  work, the importing member and the time of import. The catalog's existing "who edited and
  when" record (spec 001) MUST show the import.
- **FR-010**: A series number that clashes with an existing book in the same series MUST NOT
  block the import: the book MUST be saved without the number and flagged in the summary.
- **FR-011**: An ISBN from the site MUST be stored only if it is, or converts to, a valid
  13-digit ISBN (spec 001 FR-015); otherwise the book is saved without one.
- **FR-012**: After an import, the member MUST see a summary: how many books were added, which
  were already in the catalog, and which need a series number checked.
- **FR-013**: Selected books MUST go onto the importing member's list only, identified from
  the session, never onto another member's list. The member MUST choose one status for the
  selection (Want to read, Reading or Finished; default Finished, as in spec 001). A book
  already on their list MUST be skipped, never duplicated or changed (spec 001 FR-017).
- **FR-014**: Every member MUST be able to import, whatever their role. No cap applies to the
  number of books per import.

**Choosing sites**

- **FR-020**: An Admin MUST be able to switch each approved site on or off. Only Admins MUST be
  able to see or change this setting. The setting applies to the whole family.
- **FR-021**: On a new installation, Open Library MUST be on and Google Books off.
- **FR-022**: A site that needs a key MUST be shown as unavailable, and MUST NOT be switched
  on, while its key is not configured on the server. Keys MUST come from the server's
  environment, never from the settings screen or the browser (Constitution Principle IX).
- **FR-023**: When more than one site is on, the system MUST combine their results into one
  list, show each book once (FR-005), and show which site each book came from. When a book
  appears on both, details from the first site in the order Open Library, then Google Books,
  MUST be used, with gaps (such as a missing ISBN or series) filled from the other.
- **FR-024**: If one switched-on site fails while another answers, the member MUST see the
  results that arrived and a note naming the site that couldn't be reached.
- **FR-025**: When no site is on, the import screen MUST say import is turned off and point
  to adding books by hand.

**Working with the site**

- **FR-015**: Requests to the site MUST contain only the author name or the site's own
  identifiers: nothing about the member or the family (Constitution Principle IX).
- **FR-016**: A search or book-list request that gets no answer within 10 seconds MUST stop and
  show the "couldn't be reached" message; the rest of the app MUST keep working.
- **FR-017**: Site results for an author MUST be reused for 24 hours, so repeating a search
  within a day does not contact the site again. Reused results are kept apart from the
  catalog and are never shown as catalog content (Constitution Principle III, caching rule).
- **FR-018**: The system MUST stay within the site's published usage limits, and identify
  itself to the site as its terms ask.
- **FR-019**: The screens MUST meet WCAG 2.2 AA and work on phone, tablet and desktop, as in
  spec 001.

### Key Entities *(include if feature involves data)*

- **Source**: an approved book-data site (name, home page, terms of use). The list of
  approved sites is fixed in the application; members can't add sites.
- **Source setting**: whether each approved site is switched on, for the whole family.
  Changed by Admins only, with who changed it and when.
- **Author candidate**: an author as the site describes them (site identifier, name,
  distinguishing details). Shown during a search; never stored in the catalog.
- **Book candidate**: a work as the site describes it (site identifier, title, first
  published year, authors, series, number, ISBN). Shown for selection; stored only when the
  member confirms, and then as a catalog Book.
- **Book source reference** (catalog): links a catalog Book to the site and the site's
  identifier, with who imported it and when. One per book per site.
- **Cached lookup**: a site's answer for an author, kept for 24 hours outside the catalog.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Imported book, author, series | Catalog | All members | The importing member (on confirm) |
| Book source reference (site, site id, importer, time) | Catalog | All members | The importing member (on confirm) |
| Cached site lookups | Neither: a cache outside the catalog | The system only | The system |
| Author and book candidates | Not stored (shown during a search only) | The searching member | The system |
| Reading-list entry for an imported book (status chosen at confirm) | Personal | Owner only | Owner only (the importing member) |
| Source settings (which sites are on) | Neither: family-wide app setting | Admins | Admins |

- **Duplication check**: book data goes only into catalog tables; a reading entry holds only
  the link to the catalog book and the member's status, as in spec 001.
- **Cross-user access**: an import adds entries only to the importing member's list, with the
  owner taken from the session; it never reads or changes another member's list. Cross-user
  tests cover the import (AC-18).

## AI Involvement *(mandatory)*

- **Generated content**: None. This feature makes no AI calls. Data comes from a book-data
  site's official API.
- **Approval step**: although not AI, imported data follows the same rule: it is shown as a
  draft list and nothing is stored until the member confirms (FR-007).
- **Provenance stored**: source site, site identifier, importer and time (FR-009).
- **Fallback on failure**: adding books by hand (spec 001) always remains available.

## External Sources *(include if feature calls an external service)*

| Source | Access method | Terms of use permit this use? | Data sent |
|---|---|---|---|
| Open Library | Official API (author search, author works); no key | Yes: free API for book metadata; asks clients to identify themselves and to use data dumps, not the API, for bulk downloads ([openlibrary.org/developers/api](https://openlibrary.org/developers/api)) | Author name typed by the member; Open Library identifiers |
| Google Books | Official API (volumes search by author); free API key | Yes, with attribution, under the Google APIs Terms of Service ([developers.google.com/books/terms](https://developers.google.com/books/terms)) | Author name typed by the member; Google Books identifiers |

Both are approved; an Admin chooses which are switched on (FR-020). Each is added as an
adapter behind the common source-adapter interface (Constitution Principle IV). The plan
confirms the current terms and usage limits before implementation. The Google Books key is a
server secret, like the other secrets in the Pi's `.env`.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: None beyond recording which member imported a book, which the
  catalog's edit history (spec 001) already records for every catalog change.
- **Sent to external services**: book metadata only: the author name the member typed and the
  site's own identifiers. No login, display name, reading status, notes or ratings.

## API Changes *(include if feature changes the JSON API)*

- **New endpoints**: an author search, an author's book list, an import confirmation, and an
  Admin-only read and update of the source settings, under `/api/v1`. Exact paths are set in
  the plan and its contract files.
- **Breaking changes**: None. Existing endpoints and responses don't change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A member can add 10 books by one author to their list in under 2 minutes,
  compared with adding them one at a time by hand.
- **SC-002**: With the site answering normally, an author's book list appears within 5 seconds
  for 95% of searches, and within 1 second when the results are reused (FR-017).
- **SC-003**: Importing the same author's books twice, by one or several members, never
  creates a duplicate book, author or series in the catalog: 0 duplicates across all test
  runs.
- **SC-004**: When the site is unreachable, the member sees the failure message within 10
  seconds, and the rest of the app keeps working normally.
- **SC-005**: No request to an external site contains anything identifying a family member,
  checked by recorded-request tests on every import path.

## Clarifications

### Session 2026-11-19

- Q: Which book-data sites are approved, and can the choice be changed? → A: Both Open
  Library and Google Books; an Admin switches each on or off.
- Q: Where do the selected books go? → A: Onto the list of the member who did the search,
  and no one else's. New books also enter the shared catalog, because a list entry always
  points at a catalog book.
- Q: Who can import? → A: Any member.

## Assumptions

- **Users**: signed-in family members with accounts an Admin created (spec 001).
- **Language**: the list shows titles as the site gives them. Filtering by language is out of
  scope; a member simply doesn't select translations they don't want.
- **What counts as a book**: one entry per work, not per edition. The site's work-level data
  (title, first published year) is used; edition details beyond an ISBN are not imported.
- **Editing afterwards**: imported books are ordinary catalog books; any member can correct
  them as in spec 001.
- **Network**: the app's host (the Raspberry Pi) has outbound HTTPS to the approved sites.
  The product specification already lists this for features after 001.
- **Limits**: no per-member daily limit and no cap per import (FR-014), because no AI cost is
  involved; the 24-hour reuse of results and the sites' own limits keep traffic low.
- **Status at import**: one status for the whole selection, defaulting to Finished as when
  adding a book by hand (spec 001). Dates finished and notes are added afterwards on each
  entry as usual.
- **Numbering**: this spec takes number 002; the AI summary and covers features planned in spec
  001's roadmap will take the next free numbers.
