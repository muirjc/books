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
author. This feature lets a member look an author up on Open Library, an approved book-data
website, see that author's books, and add the ones they choose to their own reading list in
one step.
Books new to the family go into the shared catalog at the same time, because every list
entry points at a catalog book (Constitution Principle II).

This is the first feature that calls an external book-data source. It introduces the source
adapter that the planned AI summary feature will reuse. Google Books is not used here: its
terms forbid reordering or altering its results, which combining, sorting and filtering
would do (see Clarifications). The roadmap in spec 001 lists "002 – AI Summary Drafts" and
"003 – Covers and Ratings" as planned; those take the next free numbers when they are
specified.

Out of scope: Google Books and other sites; an Admin setting to choose sites; importing from
Goodreads or Kindle exports; importing by series or by title; series and ISBNs (Open
Library's work data doesn't give reliable ones, so members add them by hand); cover images
(planned for the covers feature); summaries or descriptions from the source; and automatic
or scheduled re-imports.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find an author's books and add the ones I choose (Priority: P1)

A member types an author's name, for example "Brandon Sanderson". The app asks Open Library
for that author and shows their books as a list: title, first published year and any
co-authors. Books already on the member's list, and books already in the family catalog, are
marked. The member ticks the
books they want, picks a status for them (Finished unless they change it) and confirms. The
ticked books go onto that member's list only; nothing is added before they confirm.

**Why this priority**: this is the whole feature. Without it there is nothing to import.

**Independent Test**: with Open Library replaced by recorded responses, a member
searches an author, ticks three of the books shown and confirms; exactly those three books
are on that member's list afterwards, the catalog holds one copy of each, and no other
member's list changed.

**Acceptance Criteria**:

- **AC-01**: **Given** a signed-in member, **When** they search for an author by name,
  **Then** they see that author's books from Open Library, each with its title and, where
  Open Library provides them, first published year and co-authors.
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
filters by a word in the title, selects all shown in one action, and confirms; only those
books are added.

**Acceptance Criteria**:

- **AC-10**: **Given** an author's book list, **When** the member sorts it by title or by first
  published year, or filters it by text in the title, **Then** the list updates to match.
- **AC-11**: **Given** a filtered list, **When** the member chooses "Select all shown", **Then**
  every shown book that is not already on the member's list is ticked, up to 500, and no
  hidden book is; when more than 500 are shown, the first 500 are ticked and a note says so.
- **AC-12**: **Given** the site lists several entries for one work (editions or the same title
  twice), **When** the list is shown, **Then** each work appears once.

---

### Edge Cases

- **The site is slow, down or refusing requests.** The member sees a clear message that the
  site couldn't be reached and can try again later or add books by hand; nothing changes.
  *(AC-13)*
- **Series.** Open Library's work data has no series or number in series (series appear only
  on some editions, as free text, often translated). Imported books are saved without a
  series; members add it afterwards, as for any catalog book. *(AC-14)*
- **ISBNs.** A work lists the ISBNs of all its editions, in many languages, so no single one
  is right for the family's copy. None is stored; they are used only to spot books already
  in the catalog. *(AC-15)*
- **Two members import the same book at nearly the same time.** The catalog still holds one
  copy (spec 001 FR-011). *(AC-16)*
- **The author in the catalog is a pen name** and the member searches by the writer's real
  name. The site is searched with what the member typed; the existing catalog author is
  reused only when the site's author name matches it.
- **A selected book disappears from the site** between listing and confirming. The book is
  added from what was listed; nothing is fetched again at confirm time.
- **Personal records.** Imported books go onto the importing member's list only, taken from
  the session. Other members' lists are unchanged. As for every catalog change since spec 001,
  a book shows who added it ("Last edited by"), so other members can tell someone imported it;
  the importer's status, dates, times read and notes are never shown to anyone else
  (Constitution Principle I). *(AC-18)*
- **Two selected works turn out to be one catalog book** (for example both match it by ISBN),
  or Open Library lists the same author twice on a work. The book is added once and the
  author once; the extra work is reported as a skipped duplicate. One odd entry never stops
  the rest of the import. *(AC-22)*
- **More than 500 books ticked.** The confirm is refused with "You can add up to 500 books at a
  time," and nothing is added; the member confirms in batches. *(AC-21)*
- **An author key Open Library doesn't know** (for example from an old link). The page says
  "No such author on Open Library," and nothing changes. *(AC-23)*
- **A real author Open Library lists no books for** (chosen from the search results). The
  page names the author, says "Open Library lists no books for this author," and links to
  adding a book by hand (books-0tw.4).
- **A ticked book is already on the member's list** by the time they confirm (for example
  added in another tab). It is skipped and listed in the summary as already on the list.
- **An author with thousands of entries** (for example Shakespeare). The list shows the first
  2,000 and says how many there are in all; the title filter narrows those 2,000. Works beyond
  them can't be imported from this list and are added by hand. *(AC-20)*
- **The listed results expire** (after 24 hours) before the member confirms. Nothing is
  added; they are asked to reload the list, so no book is imported from stale data. A list is
  normally never shown with less than an hour left, so this needs a page left open for an
  hour or more. The exception: if the site can't be reached when a list with under an hour
  left would be fetched again, the earlier list is still shown, with a note that it expires
  within the hour, rather than no list at all.

- **AC-13**: **Given** the site times out or returns an error, **When** the member searches or
  loads an author's books, **Then** they see "The book site couldn't be reached. Try again
  later, or add the book by hand," and nothing is added.
- **AC-14**: **Given** an imported book, **When** it is added, **Then** it has no series and no
  ISBN, and a member can add them afterwards on the book's page.
- **AC-15**: **Given** a catalog book whose ISBN is one of the ISBNs Open Library lists for a
  work, **When** that work is shown, **Then** it is marked "In the family catalog" and
  confirming it creates no second copy.
- **AC-16**: **Given** two members confirming the same new book at the same time, **When** both
  imports finish, **Then** the catalog holds that book once and both members see it as
  imported.
- **AC-20**: **Given** an author with more than 2,000 works on Open Library, **When** their
  books are listed, **Then** the first 2,000 are shown with a note giving the total and saying
  that works beyond them can be added by hand.
- **AC-21**: **Given** more than 500 books ticked, **When** the member confirms, **Then** they
  see "You can add up to 500 books at a time," and nothing is added.
- **AC-22**: **Given** a selection in which two works resolve to the same catalog book, or a
  work lists the same author twice, **When** the member confirms, **Then** every other book
  is added, the book is added once with the author once, and the summary lists the extra work
  as a skipped duplicate.
- **AC-23**: **Given** an author key that Open Library doesn't know, **When** the member opens
  that author's works, **Then** they see "No such author on Open Library," and nothing
  changes.

## Requirements *(mandatory)*

### Functional Requirements

**Searching**

- **FR-001**: Any signed-in member MUST be able to search Open Library for an author by name.
  Open Library is the only site the feature may contact.
- **FR-002**: When a name matches more than one author on the site, the system MUST list the
  matches with distinguishing details (such as birth and death years, a well-known title and
  the number of books) and let the member choose one.
- **FR-003**: For the chosen author, the system MUST list their books with title, and where
  Open Library provides them, first published year and co-authors.
- **FR-004**: The list MUST show each work once, even when the site lists several editions.
- **FR-005**: The list MUST mark books already on the member's own list (which can't be
  selected) and books already in the catalog. A book counts as already in the catalog when it
  has the same Open Library identifier as a catalog book, or any of its editions' ISBNs
  (converted to 13 digits where possible) matches a catalog book's ISBN, or the same title
  (ignoring capitalization, punctuation and a leading "The", "A" or "An") and the same first
  author.
- **FR-006**: The member MUST be able to sort the list by title or first published year,
  filter it by title text, and select all shown books at once (up to 500, FR-014).

**Importing**

- **FR-007**: Nothing MUST be written to the catalog until the member confirms their selection.
- **FR-008**: On confirmation, the system MUST add each selected book that is not already in the
  catalog, with its title and its authors in Open Library's order. Existing authors MUST be
  reused (matching names ignoring capitalization), per spec 001 FR-011. It MUST then add
  every selected book to the importing member's own list.
- **FR-009**: Every imported book MUST record the source site, the site's identifier for the
  work, the importing member and the time of import. The catalog's existing "who edited and
  when" record (spec 001) MUST show the import.
- **FR-010**: Imported books MUST be saved without a series or number in series; Open Library's
  work data doesn't provide them reliably.
- **FR-011**: Imported books MUST be saved without an ISBN. Edition ISBNs from Open Library are
  used only for matching (FR-005) and are not stored.
- **FR-012**: After an import, the member MUST see a summary: how many books were added to
  their list, how many of those were new to the catalog, and which were skipped because they
  were already on their list or were the same book as another selected work (FR-021).
- **FR-013**: Selected books MUST go onto the importing member's list only, identified from
  the session, never onto another member's list. The member MUST choose one status for the
  selection (Want to read, Reading or Finished; default Finished, as in spec 001). A book
  already on their list MUST be skipped, never duplicated or changed (spec 001 FR-017).
- **FR-014**: Every member MUST be able to import, whatever their role. One confirm MUST add at
  most 500 books; more are added by confirming again.

**Working with the site**

- **FR-015**: Requests to Open Library MUST contain only the author name or Open Library's own
  identifiers: nothing about the member or the family (Constitution Principle IX).
- **FR-016**: A search or book-list request that gets no answer within 10 seconds, counting
  every call to Open Library it makes, MUST stop and show the "couldn't be reached" message;
  the rest of the app MUST keep working.
- **FR-017**: Open Library's results for an author MUST be reused for 24 hours, so repeating a
  search within a day does not contact the site again. Reused results are kept apart from the
  catalog and are never shown as catalog content (Constitution Principle III, caching rule).
- **FR-018**: The system MUST stay within Open Library's published usage limits (about 1
  request a second for requests without a contact address), and name itself in a User-Agent
  that contains no contact address or other detail about the family.
- **FR-019**: The screens MUST meet WCAG 2.2 AA and work on phone, tablet and desktop, as in
  spec 001.
- **FR-020**: An author's list MUST show at most 2,000 works, with a note giving the total when
  Open Library has more and saying that the rest can be added by hand.
- **FR-021**: One odd entry MUST NOT stop an import: works that resolve to a book already being
  added are skipped and reported, and an author listed twice on a work is added once.
- **FR-022**: Titles and author names from Open Library MUST be stored in the same normalized
  form used for matching, and cut to fit the catalog's limits (300 characters for a title, 200
  for a name).

### Key Entities *(include if feature involves data)*

- **Source**: an approved book-data site (name, home page, terms of use). Open Library is the
  only one; it is fixed in the application, and members can't add sites.
- **Author candidate**: an author as the site describes them (site identifier, name,
  distinguishing details). Shown during a search; never stored in the catalog.
- **Book candidate**: a work as the site describes it (site identifier, title, first
  published year, authors, and its editions' ISBNs for matching only). Shown for selection;
  stored only when the member confirms, and then as a catalog Book.
- **Book source reference** (catalog): links a catalog Book to the site and the site's
  identifier, with who imported it and when. One per book per site.
- **Cached lookup**: a site's answer for an author, kept for 24 hours outside the catalog.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Imported book and its authors | Catalog | All members | The importing member (on confirm) |
| Book source reference (site, site id, importer, time) | Catalog | All members | The importing member (on confirm) |
| Cached site lookups | Neither: a cache outside the catalog | The system only | The system |
| Author and book candidates | Not stored (shown during a search only) | The searching member | The system |
| Reading-list entry for an imported book (status chosen at confirm) | Personal | Owner only | Owner only (the importing member) |

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

Open Library is added as an adapter behind the common source-adapter interface
(Constitution Principle IV). Requests name the app in a User-Agent, as Open Library asks, but
carry no contact address, since that would identify a family member (Principle IX). Open
Library's limit for such requests is about 1 a second, which this feature stays within.

Google Books was considered and left out: its branding guidelines say results "may not be
reordered or otherwise altered" and need a "Powered by Google" badge beside them
([developers.google.com/books/branding](https://developers.google.com/books/branding)),
which conflicts with FR-004 to FR-006. It can be added later, behind the same interface, for
a use that shows its results unaltered.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: None beyond recording which member imported a book, which the
  catalog's edit history (spec 001) already records for every catalog change.
- **Sent to external services**: book metadata only: the author name the member typed and the
  site's own identifiers. No login, display name, reading status, notes or ratings.

## API Changes *(include if feature changes the JSON API)*

- **New endpoints**: an author search, an author's book list and an import confirmation,
  under `/api/v1`. Exact paths are set in the plan and its contract files.
- **Breaking changes**: None. Existing endpoints and responses don't change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A member can add 10 books by one author to their list in under 2 minutes,
  compared with adding them one at a time by hand.
- **SC-002**: With the site answering normally, an author's book list appears within 5 seconds
  for 95% of searches, and within 1 second when the results are reused (FR-017).
- **SC-003**: Importing the same author's books twice, by one or several members, never
  creates a duplicate book or author in the catalog: 0 duplicates across all test runs.
- **SC-004**: When the site is unreachable, the member sees the failure message within 10
  seconds, and the rest of the app keeps working normally.
- **SC-005**: No request to an external site contains anything identifying a family member,
  checked by recorded-request tests on every import path.
- **SC-006**: Confirming 200 selected books finishes within 10 seconds on the family's server,
  and confirming the maximum of 500 within 25 seconds.

## Clarifications

### Session 2026-11-19

- Q: Which book-data sites are approved, and can the choice be changed? → A: First answered
  "both Open Library and Google Books, switched on and off by an Admin". During planning,
  Google Books' terms turned out to forbid reordering or altering its results, so the answer
  was changed to **Open Library only**, with no Admin site setting (decision books-zl3;
  Google Books follow-up books-395).
- Planning finding (2026-11-19): Open Library's search returns no series fields, and its ISBNs
  are per edition and in many languages. Series and ISBNs are therefore not imported; ISBNs
  are used only to spot books already in the catalog (FR-010, FR-011).
- Q: Where do the selected books go? → A: Onto the list of the member who did the search,
  and no one else's. New books also enter the shared catalog, because a list entry always
  points at a catalog book.
- Q: Who can import? → A: Any member.
- Review of PR #9 (2026-11-19): Q: How large can one import be? → A: At most 500 books per
  confirm, because larger forms exceed the web server's form and header limits; import more by
  confirming again. Q: May other members see who imported a book? → A: Yes, as for every
  catalog change since spec 001; never the importer's status, dates or notes.

## Assumptions

- **Users**: signed-in family members with accounts an Admin created (spec 001).
- **Language**: the list shows titles as the site gives them. Filtering by language is out of
  scope; a member simply doesn't select translations they don't want.
- **What counts as a book**: one entry per work, not per edition. Only work-level data (title,
  first published year, authors) is imported.
- **Editing afterwards**: imported books are ordinary catalog books; any member can correct
  them as in spec 001.
- **Network**: the app's host (the Raspberry Pi) has outbound HTTPS to the approved sites.
  The product specification already lists this for features after 001.
- **Limits**: no per-member daily limit, because no AI cost is involved; at most 500 books per
  confirm (FR-014) for the web server's form limits; the 24-hour reuse of results and Open
  Library's own limits keep traffic low.
- **Status at import**: one status for the whole selection, defaulting to Finished as when
  adding a book by hand (spec 001). Dates finished and notes are added afterwards on each
  entry as usual.
- **Numbering**: this spec takes number 002; the AI summary and covers features planned in spec
  001's roadmap will take the next free numbers.
