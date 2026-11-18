# Feature Specification: Family Reading List

**Feature Branch**: `001-family-reading-list`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "take /docs/Family Book Tracker - Specification.md as the input for the initial and upcoming specifications. This will be the first spec. We can move on from here"

**Source document**: [Family Book Tracker – Specification](../../docs/Family%20Book%20Tracker%20–%20Specification.md)
(v0.1). Requirement and criterion references in brackets, such as *[doc FR-03]*, point to
that document.

## Scope

This is the first of several specs built from the source document. It delivers the core of
the product: family accounts, the shared catalog of books, authors and series, and each
member's private reading list. Summaries can be written by hand.

| Spec | Contents | Source requirements |
|---|---|---|
| **001 – Family Reading List (this spec)** | Sign-in, account management, shared catalog, pen names, personal lists, browse/search, reading status and notes, manual summaries, optional ISBN | doc FR-01 – FR-06, FR-09 – FR-13, FR-15; doc AC-01 – AC-06, AC-09 |
| 002 – AI Summary Drafts (planned) | AI-drafted summaries with review, series suggestions, book data sources | doc FR-07, FR-08, FR-14; doc AC-07, AC-08 |
| 003 – Covers and Ratings (planned) | Cover images, personal 1–5 rating | doc FR-16, FR-17 |

Out of scope for v1 (from the source document): native mobile apps, sharing outside the
family, social features, recommendations, and importing from Goodreads or Kindle.

## Clarifications

### Session 2026-11-18

- Q: Who should be allowed to edit a shared catalog book, author or series after it has been
  added? → A: Any member; each edit records who made it and when.
- Q: What should happen after repeated wrong passwords at sign-in? → A: After 5 wrong
  attempts for a login, sign-in for that login is blocked for 15 minutes.
- Q: What password rule should apply to accounts, including young children's? → A: At least
  8 characters for every account, with no other complexity rules.
- Q: Should a member be able to record reading the same book more than once? → A: Yes, as a
  times-read count on the single entry, with the latest date finished.
- Q: What accessibility standard should the screens meet? → A: WCAG 2.2 level AA.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sign in and keep my own reading list (Priority: P1)

A family member signs in with the account a parent created for them, adds the books they
have read, and sees a list that contains only their own books. Another member using the
same app sees only theirs.

**Why this priority**: a private, per-person list is the core promise of the product.
Everything else builds on it.

**Independent Test**: with two accounts created at setup, each member signs in, adds books
and confirms that their list contains only their own entries and that the other member's
entries cannot be reached.

**Acceptance Criteria**:

- **AC-01**: **Given** a member with an active account, **When** they enter their login and
  password, **Then** they are signed in and see their own reading list. *[doc FR-01]*
- **AC-02**: **Given** a signed-in member, **When** they sign out, **Then** their list can no
  longer be viewed until someone signs in again. *[doc FR-01]*
- **AC-03**: **Given** a signed-in member, **When** they add a book with a title and one
  author only, **Then** it is saved and appears in their list with series and number in
  series blank. *[doc AC-02]*
- **AC-04**: **Given** Alice and Ben each have books on their lists, **When** Alice views her
  list, **Then** she sees only her entries; **and when** Alice requests one of Ben's entries
  directly, **Then** she gets a "not found" result that does not reveal the entry exists.
  *[doc AC-01]*
- **AC-05**: **Given** a book already on a member's list, **When** they add the same book
  again, **Then** they see "Already on your list" and nothing new is created. *[doc AC-05]*
- **AC-06**: **Given** a member enters a number in series without choosing a series, **When**
  they save, **Then** the form shows a validation error and nothing is saved. *[doc AC-03]*
- **AC-07**: **Given** a book on a member's list, **When** they remove it, **Then** it
  disappears from their list but stays in the family catalog and on other members' lists.
  *[doc FR-10]*
- **AC-08**: **Given** a book on a member's list, **When** they set its status, date finished
  and notes, **Then** those details are saved and shown only to that member. *[doc FR-13]*
- **AC-31**: **Given** a member adding a book, **When** they leave the status unset, **Then** it
  is saved as Finished; **and when** they enter a date finished in the future, **Then** it is
  rejected with a validation message. *[doc §5 reading_entry]*
- **AC-35**: **Given** a Finished book on a member's list with times read 1, **When** they
  choose "Read again" and later mark it Finished on a new date, **Then** the list shows times
  read 2 and the new date finished, still as a single entry.

---

### User Story 2 - Parents manage family accounts (Priority: P1)

A parent with the Admin role creates accounts for each family member (children without an
email address), and can deactivate an account or reset a forgotten password. Nobody can
create their own account.

**Why this priority**: without accounts no one can sign in; it is required for User Story 1
to be usable by a real family.

**Independent Test**: the initial Admin creates a member account, the member signs in, the
Admin resets the member's password and later deactivates the account; each step is checked
from the member's side.

**Acceptance Criteria**:

- **AC-09**: **Given** a signed-in Admin, **When** they create an account with a display name,
  a username (no email) and an initial password, **Then** that person can sign in with it and
  is asked to choose their own password before continuing. *[doc FR-02]*
- **AC-10**: **Given** an account an Admin has deactivated, **When** its owner tries to sign
  in, **Then** sign-in is refused, **and** the account's reading entries are kept and
  reappear if the account is reactivated. *[doc AC-09]*
- **AC-11**: **Given** an Admin has reset a member's password, **When** the member signs in
  with the temporary password, **Then** they must choose a new password before continuing.
  *[doc FR-02]*
- **AC-12**: **Given** a person who is not signed in, **When** they look for a way to create
  an account, **Then** none is offered. *[doc §2]*
- **AC-13**: **Given** a member without the Admin role, **When** they try to reach account
  management, **Then** access is refused. *[doc §2]*
- **AC-14**: **Given** a signed-in Admin, **When** they look at another member's reading
  list or notes, **Then** they cannot see it; Admin rights cover accounts only. *[doc §2]*
- **AC-26**: **Given** only one active Admin, **When** that Admin tries to deactivate their own
  account or remove their Admin role, **Then** it is refused with an explanation.
- **AC-27**: **Given** a newly installed application with no accounts, **When** installation
  completes, **Then** exactly one Admin account exists and can sign in.
- **AC-28**: **Given** a member signed in on a shared device, **When** they choose "Switch
  user", **Then** they are signed out and the sign-in screen lists the profiles recently used
  on that device; choosing one fills in its login and still asks for the password.
  *[doc §2]*
- **AC-29**: **Given** an existing login "Sam", **When** an Admin creates an account with the
  login "sam", **Then** it is rejected as already in use.
- **AC-33**: **Given** 5 wrong passwords have been entered for a login, **When** anyone tries to
  sign in with that login in the next 15 minutes, even with the correct password, **Then**
  sign-in is refused with a "try again later" message; **and after** 15 minutes the correct
  password works.
- **AC-34**: **Given** an Admin creating an account or a member choosing a new password,
  **When** they enter a password shorter than 8 characters, **Then** it is rejected; **and
  when** they enter an 8-character password of only lowercase letters, **Then** it is
  accepted.

---

### User Story 3 - Add books from a shared family catalog (Priority: P2)

When a member types an author, series or book title, the app suggests matching entries
that anyone in the family has already added, so the same book is not entered twice. Authors
can be marked as pen names, optionally with the writer's real name.

**Why this priority**: it cuts typing and keeps the catalog clean, but members can already
keep lists without it.

**Independent Test**: Alice adds a book; Ben starts adding the same book, picks the
suggestion and confirms the catalog still holds one copy. A pen-name author is saved without
a real name, the real name is added later, and a search by real name finds the books.

**Acceptance Criteria**:

- **AC-15**: **Given** Alice has added a book, **When** Ben starts typing its title or
  author, **Then** the existing book is suggested, and choosing it adds it to Ben's list
  without creating a second catalog book. *[doc AC-06]*
- **AC-16**: **Given** an author or series name already in the catalog, **When** a member
  tries to create a new one with the same name (ignoring capitalization), **Then** they are
  pointed to the existing entry instead. *[doc FR-04]*
- **AC-17**: **Given** a member adding an author, **When** they mark the author as a pen name
  and leave the real name blank, **Then** the author is saved; **and when** a real name is
  added later, **Then** searching by the real name finds that author's books. *[doc AC-04]*
- **AC-18**: **Given** an author not marked as a pen name, **When** a member enters a real
  name, **Then** it is rejected with a message to mark the author as a pen name first.
  *[doc FR-06]*
- **AC-19**: **Given** a series that already has a book at a given number, **When** a member
  assigns another book the same number in that series, **Then** it is rejected with a message
  naming the existing book. *[doc §5]*
- **AC-20**: **Given** a member enters a decimal number in series such as 2.5 for a book in a
  series, **When** they save, **Then** it is accepted and the book sorts between 2 and 3.
  *[doc FR-05]*
- **AC-30**: **Given** a member adding a book, **When** they enter an ISBN that is not a valid
  13-digit ISBN, **Then** it is rejected; **and when** they enter an ISBN already used by a
  catalog book, **Then** that existing book is offered instead. *[doc FR-15]*
- **AC-32**: **Given** a book Alice added, **When** Ben corrects its title, **Then** the new
  title appears on every member's list and the book shows Ben as the last editor, with the
  date.

---

### User Story 4 - Browse, sort, filter and search my list (Priority: P3)

A member finds books in their own list by sorting, filtering and searching, and sees each
series they have read in reading order.

**Why this priority**: useful once a list grows, but a short list is usable without it.

**Independent Test**: with a seeded list of books across several authors and series, the
member sorts, filters, searches and opens a series view, and checks that only their own
books appear in each result.

**Acceptance Criteria**:

- **AC-21**: **Given** a member's list, **When** they sort by title, author or series, or
  filter by author, series or status, **Then** only their own matching entries are shown in
  that order. *[doc FR-09]*
- **AC-22**: **Given** a member has read books 1, 2.5 and 3 of a series and another book in it
  without a number, **When** they open that series, **Then** the books are listed 1, 2.5, 3,
  followed by the unnumbered book. *[doc FR-09]*
- **AC-23**: **Given** a member's list, **When** they search for text matching a title, an
  author's name, an author's real name or a series name, **Then** matching entries from
  their own list are shown, and no entries from other members' lists. *[doc FR-12]*

---

### User Story 5 - Write and keep a book summary (Priority: P3)

Any member can write a short summary for a book in the catalog. The family shares one
current summary per book; earlier versions are kept.

**Why this priority**: summaries add value but are optional; AI drafting follows in spec 002.

**Independent Test**: a member writes a summary for a book, another member sees it, then
replaces it; the latest version is shown and the earlier one is retained.

**Acceptance Criteria**:

- **AC-24**: **Given** a book in the catalog, **When** a member writes and saves a summary,
  **Then** every family member viewing the book sees it, recorded as written by hand, by
  that member, with the date. *[doc FR-03, §5 book_summary]*
- **AC-25**: **Given** a book with a summary, **When** a member saves a new one, **Then** the
  new summary becomes the one shown and the previous one is kept in the book's history.
  *[doc §5 book_summary]*

---

### Edge Cases

- A member requests another member's entry, or an entry that never existed: both give the
  same "not found" result (AC-04).
- An account is deactivated while its owner is signed in: their next action signs them out.
- An Admin tries to deactivate or remove the Admin role from the last active Admin: refused,
  so the family is never locked out of account management.
- Two members create the same new author at nearly the same moment: one is saved; the other
  is shown the existing author instead of an error.
- A member edits an author or series name to match an existing one: rejected with a pointer
  to the existing entry.
- Two different books share a title but have different authors: both are allowed.
- A member removes a book from their list and later adds it again: allowed; the old status
  and notes are not restored.
- A number in series is negative, has more than two decimal places, or exceeds 999.99:
  rejected with a validation message.
- A date finished in the future: rejected.
- A login that differs from an existing one only by capitalization: rejected as already in
  use.
- An ISBN that is not a valid 13-digit ISBN, or is already used by another catalog book:
  rejected, and in the second case the existing book is offered.

## Requirements *(mandatory)*

### Functional Requirements

**Accounts and sign-in**

- **FR-001**: The system MUST let a member sign in with a login (email address or username)
  and password, and sign out. *[doc FR-01]*
- **FR-002**: The system MUST refuse sign-in for a deactivated account and MUST keep that
  account's reading entries and catalog contributions. *[doc FR-02, AC-09]*
- **FR-003**: Only an Admin MUST be able to create accounts, giving a display name, a login, a
  role (Member or Admin) and an initial password. An email address MUST NOT be required.
  There MUST be no self-registration. The initial password is temporary and MUST be changed at
  the first sign-in; the only exception is the first Admin created at installation (FR-006),
  who chooses their own password. *[doc FR-02, §2]*
- **FR-004**: An Admin MUST be able to deactivate and reactivate accounts and reset a
  member's password. A reset password is temporary and MUST be changed at the next sign-in.
  *[doc FR-02]*
- **FR-005**: The system MUST NOT allow the last active Admin account to be deactivated or
  lose the Admin role.
- **FR-006**: The first Admin account MUST be created as part of installing the application.
- **FR-007**: The system MUST offer a "Switch user" action that signs the current member out
  and shows the sign-in screen with the profiles used on that device in the last 90 days, up
  to 5, most recent first, leaving out deactivated accounts. Choosing a profile fills in the
  login; the password is still required. *[doc §2]*
- **FR-008**: Logins MUST be unique, ignoring capitalization.
- **FR-027**: After 5 consecutive wrong passwords for a login, the system MUST block sign-in
  for that login for 15 minutes, even with the correct password. The message MUST be the
  same whether or not the login exists. A successful sign-in resets the count. Attempts made
  while sign-in is blocked are refused without being counted and do not extend the block.
- **FR-028**: Every password, including initial and temporary passwords set by an Admin, MUST
  be at least 8 characters, with no maximum below 64 and no other complexity rules.

**Shared catalog**

- **FR-009**: Books, authors, series and summaries MUST form one catalog shared by the whole
  family. Any member MAY add or edit any catalog entry, and changes are visible to all
  members. Each catalog entry MUST record who created it and who last edited it, with when.
  *[doc §1, §2]*
- **FR-010**: When a member enters a book title, author or series, the system MUST suggest
  matching catalog entries as they type and let them create a new entry when none match.
  Author suggestions MUST match both the name and the real name. *[doc FR-04]*
- **FR-011**: The catalog MUST NOT hold two authors with the same name, two series with the
  same name (both ignoring capitalization), two books with the same ISBN, or two books with
  the same number in the same series. *[doc §5]*
- **FR-012**: A book MUST have a title and one or more authors in a stated order, and MAY
  have a series, a number in series and an ISBN. *[doc FR-03, FR-15]*
- **FR-013**: A number in series MUST accept values from 0 to 999.99 with up to two decimal
  places, and MUST only be allowed when a series is set. *[doc FR-05]*
- **FR-014**: An author MUST be able to be marked as a pen name with an optional real name.
  A real name MUST only be allowed on an author marked as a pen name. *[doc FR-06]*
- **FR-015**: An ISBN, when given, MUST be a valid 13-digit ISBN. *[doc FR-15]*

**Personal reading list**

- **FR-016**: A member MUST be able to add a catalog book to their own list, either by choosing
  an existing book or by entering a new one in the same step. *[doc FR-03]*
- **FR-017**: A book MUST NOT appear more than once in one member's list; a repeat attempt
  MUST show "Already on your list", change nothing, and offer to record a re-read instead.
  *[doc FR-11, AC-05]*
- **FR-018**: Each list entry MUST hold a status (Want to read, Reading or Finished; default
  Finished), an optional date finished (not in the future), a times-read count and optional
  private notes. *[doc FR-13]*
- **FR-029**: The times-read count MUST be a whole number from 0 to 99. It MUST start at 1 for
  a book added as Finished and 0 otherwise, and MUST go up by one each time the entry's
  status changes to Finished. "Read again" MUST set the status to Reading without changing
  the count. The date finished MUST hold the most recent finish. A member MAY edit the count
  directly to record past reads.
- **FR-019**: A member MUST be able to edit and remove their own entries. Removing an entry
  MUST NOT remove the book from the catalog. *[doc FR-10]*
- **FR-020**: A member MUST only ever see or change their own entries and notes. A request
  for another member's entry MUST give the same "not found" result as an entry that does
  not exist. Admin rights MUST NOT be an exception. *[doc §2, AC-01]*

**Browsing and search**

- **FR-021**: A member MUST be able to sort their list by title, author, series or date
  finished and filter
  it by author, series or status. *[doc FR-09]*
- **FR-022**: A series view MUST list the member's books in that series by number, with
  unnumbered books after the numbered ones. *[doc FR-09]*
- **FR-023**: A member MUST be able to search their list by title, author name, author real
  name and series name. *[doc FR-12]*

**Summaries**

- **FR-024**: Any member MUST be able to write a summary for a catalog book. Each book has at
  most one current summary, shared by the family; earlier summaries MUST be kept as history.
  *[doc FR-03, §5]*
- **FR-025**: Each saved summary MUST record that it was written by hand, who wrote it and
  when. *[Constitution III]*

**General**

- **FR-026**: All screens MUST be usable on phone, tablet and desktop browsers. *[doc §7]*
- **FR-030**: All screens MUST meet WCAG 2.2 level AA, including full use by keyboard alone
  and labels that screen readers announce for every form field and control.

### Key Entities *(include if feature involves data)*

- **Family member account**: a person who can sign in. Display name, login, role (Member or
  Admin), active or deactivated. Children's accounts have a username rather than an email.
- **Author**: a name printed on books, with a sort name. May be marked as a pen name and
  optionally carry the writer's real name.
- **Series**: a named sequence of books.
- **Book**: a catalog entry with a title, one or more authors in order, an optional series
  and number in series, and an optional ISBN.
- **Summary**: a short description of a book, shared by the family. One current version per
  book plus history; records how it was written, by whom and when.
- **Reading entry**: the personal record linking one member to one book, with status, date
  finished (most recent), times read and notes. Belongs to exactly one member.
- Books, authors and series each record who created them and who last edited them, with when.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Books, authors, series | Catalog | All members | Any member |
| Summaries and their history | Catalog | All members | Any member |
| Reading entries (status, date finished, times read, notes) | Personal | Owner only | Owner only |
| Account details (display name, login, role, status) | Account | The owner and Admins | Admins (and the owner, for their own password) |
| Recently used profiles on a device | Device | Anyone using that device | The app, at sign-in |

- **Duplication check**: reading entries refer to catalog books; no book, author or series
  data is copied into personal records.
- **Cross-user access**: no member, including an Admin, can see or change another member's
  reading entries or notes.

## AI Involvement *(mandatory)*

- **Generated content**: None. All summaries in this spec are written by hand. AI-drafted
  summaries and series suggestions are specified in 002 – AI Summary Drafts.

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: display name, login (email address or username), password
  (stored only in a form that cannot be reversed), role, and each member's private notes.
  Email addresses are optional, so children's accounts need none.
- **Recently used profiles**: the display name and login of members who signed in recently
  are remembered on that device only, to support "Switch user".
- **Sent to external services**: None. This spec uses no external services.

## API Changes *(include if feature changes the JSON API)*

- **New endpoints**: the initial API for sign-in, account management, the catalog and the
  member's own list. The source document's §6 is the starting outline; the plan defines the
  contract.
- **Breaking changes**: None (first release).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A signed-in member can add a book that is already in the catalog in under 30
  seconds, and a new book with title, author and series in under one minute.
- **SC-002**: A member's list, sorted or filtered, appears in under 1 second for 95% of page
  loads when the catalog holds 5,000 books.
- **SC-003**: In acceptance testing, no member can view or change any other member's entries
  or notes, on any screen or by direct request (zero leaks).
- **SC-004**: When a member adds a book another member already added, choosing the suggestion
  results in no duplicate book, author or series in the catalog in 100% of test runs.
- **SC-005**: At least 4 out of 5 family members, including a child, add their first book
  without help.
- **SC-006**: Every screen is usable without horizontal scrolling on a phone-sized screen.
- **SC-007**: Every screen passes an automated WCAG 2.2 AA check with no violations, and the
  main journeys (sign in, add a book, edit an entry, switch user) can be completed using
  only a keyboard.
- **SC-008**: Suggestions appear within 0.3 seconds of typing for 95% of type-ahead lookups
  when the catalog holds 5,000 books.

## Assumptions

- **Visibility**: members cannot see each other's lists in v1, even read-only. *[doc open
  question 1]*
- **Summaries**: one shared summary per book, not one per reader; personal impressions go in
  notes. *[doc open question 2]*
- **Re-reads**: a book appears once per member list; re-reads are counted on that entry, with
  only the latest date finished kept. Per-read history is not kept. *[doc open question 3]*
- **Pen names**: a free-text real name is enough; linking pen names to one another is left for
  later. *[doc open question 4]*
- **Children's accounts**: children use the same screens as adults, with no parental review
  of what they add. *[doc open question 6]*
- **Hosting**: decided in source document v0.2, section 10. The app runs on a Raspberry Pi 5
  at home, reachable only from the family network. That doesn't change this spec's behaviour;
  the deployment work (arm64 images, `/healthz`, Compose, HTTPS, backups) is tracked
  separately. *[doc open question 5]*
- **Password reset**: an Admin sets a temporary password and tells the member in person;
  there is no emailed reset link, since children may have no email.
- **Sign-in with Google**: not included; the source document lists it as a later option.
- **Catalog deletion**: members cannot delete catalog books, authors or series in v1; they
  can only remove books from their own list.
- **Sessions**: a member stays signed in on a device until they sign out or 14 days pass
  without use.
