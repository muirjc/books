# Research: Favorite Author Shortcuts (spec 017)

## R1 – The star button

- **Decision**: a small form per author, posting to the existing
  `POST /authors/{author_id}/favorite` with:
  - `favorite=yes|no`, as today;
  - a new optional `back` field: the page to return to.

  Its button holds a decorative ☆ or ★ (`aria-hidden`) and visually hidden text "Add
  <author> to my favorite authors" or "Remove <author> from my favorite authors" (AC-04).
  It's a plain form, so it works without JavaScript.

  It's placed:
  - on the book page, straight after each author's name in the byline, before any "pen
    name of …" note (the name and star never wrap apart, and the note may wrap, R6);
  - on the entry page, after the author's name on each "All books by <author>" line in
    More.
- **Rationale**: reusing the spec 011 route keeps one place that changes favorites, with
  its 404 for unknown authors and its idempotent add and remove. A button with hidden text
  gives a clear accessible name.
- **Alternatives considered**:
  - **A separate route per page**: rejected, because it duplicates the spec 011 logic.
  - **`aria-pressed` toggle**: rejected. A toggle's name must stay the same in both
    states, so it can't say "Add" or "Remove". After the full page reload the name
    already says which state the author is in.
  - **HTMX in-place swap**: not needed. The reload with an anchor keeps the reader's
    place, and the page must work without JavaScript anyway.

## R2 – Where the favorite change returns to

- **Decision**: a new module, `web/favorites.py`, holds the return-address rules, as
  `web/quick.py` does for spec 015.
  - **Accepted `back` paths** (a full match of a fixed pattern, with no `//`):
    - `/books/<uuid>` (an author page gets the spec 011 `?msg=` address instead, whose
      notice it shows; PR #42 review);
    - `/entries/<uuid>`, only when that entry is the viewer's own. This is checked
      through `ReadingEntryRepository(db, session user).get`, so another member's entry
      is refused exactly like an unknown one (AC-05, Principle I);
    - `/` (My books, with its query), `/series/<uuid>`, and `/books/add` (the pages the
      offer shows on, R4).
  - **Anything else** returns to `/authors/<id>?msg=…`, exactly as today, so the spec 011
    behaviour and tests are unchanged when `back` is absent.
- **Notice keys**:
  - **Removed from the return address**: one-time keys (`msg`, `favorited`,
    `unfavorited`, and spec 015's `wanted`/`already`) are dropped from `back`.
  - **Kept**: `finished` (R4) stays, so other qualifying authors are still offered after
    one is accepted (AC-08, AC-10).
  - **Added**: `favorited=<author_id>` or `unfavorited=<author_id>`.
- **Anchor**: the redirect ends in `#favorite-notice` when the notice will show near the
  control, so the reader stays where they were (AC-03).
- **Query validation** (Constitution VII): `finished`, `favorited` and `unfavorited` are
  read through `FavoriteNoticeQuery`, a Pydantic v2 model in `schemas/catalog.py`. Each
  field is an optional UUID, and an invalid value becomes none rather than an error, so
  a mangled address shows the page without a notice or offer. Services only ever receive
  validated UUIDs.
- **Notice text**: the landing page looks up the author by id and shows "Added <author> to
  your favorite authors." or "Removed <author> from your favorite authors." An unknown id
  shows nothing.
- **Alternatives considered**:
  - **Reusing `quick._BACK`**: rejected. Its targets and its fallback (the Catalog)
    differ, and an entry page needs the ownership check.
  - **The `Referer` header**: rejected. It's unreliable and can be stripped.

## R3 – Counting my finished books by an author

- **Decision**: `ReadingEntryRepository.finished_counts(author_ids)`. It's one grouped
  query over my own entries (`status = 'finished'`), joined to `book_author`, and returns
  `{author_id: count}`.
  - **Re-reads count once** (AC-09): `reading_entry` is unique on (user, book), so a
    re-read is the same entry, and the query counts each book once.
  - **Stories don't count**: only `book_author` is joined, not story authors (edge case).
- **My favorites among some authors**: `FavoriteAuthorRepository.among(author_ids)`
  returns the subset that are my favorites. It's one query, used by the stars and the
  offer.
- **Rationale**:
  - Both repositories are already bound to the session user (Principle I) and are
    coverage-critical.
  - Each query is one indexed statement over at most a handful of authors, so it fits
    the 1 s budget (AC-15).

## R4 – The offer after finishing

- **When a save finishes a book**: the save adds `finished=<book_id>` to the address it
  redirects to:
  - **Add a book** with status Finished. The book is new to my list, so it always counts
    as becoming finished. Every redirect is covered: My books, a series page, Add
    another, and the entry page after `stories_not_added`.
  - **Saving my entry** when its status was not Finished and is now Finished.
- **Never**:
  - when the entry was already finished, or the new status isn't Finished;
  - for an import (spec 002), whose redirects are untouched;
  - for the spec 015 quick add (Want to read).
- **Showing the offer**: each landing page calls `favorites.offer(request, db, auth)`.
  - It reads `finished=<book_id>`, then checks live that my entry for that book exists
    and is finished. Otherwise it returns nothing.
  - For each of the book's authors that is not among my favorites and whose finished
    count is 2 or more, it returns `(author, count)`.
  - Since it's worked out live, a reload of the same address shows the offer again but
    never offers an author who has become a favorite (Clarifications).
  - A hand-made `finished=` address can only show offers that are true for me, so it
    reveals nothing.
- **Pages**: `partials/favorite_offer.html` is a `role="status"` region with one line and
  one button per author. Each button is in its own form, with the page's CSRF token (as
  every state-changing form has), and posts to the favorite route with `back` set to the
  current page (its path and query) and returns to `#favorite-notice`. It's included on
  my entry page, My books (the full page, not the HTMX list partial), series pages, and
  Add a book when `after=` is present.
- **Rationale**: the offer rides on the address, as the app's other notices do, so no
  session state is needed (Clarifications, 2026-11-25).
- **`DROPPED_KEYS`**: spec 015's `DROPPED_KEYS` gains `finished`, `favorited` and
  `unfavorited`. A quick add from a page that has an offer then doesn't carry the offer
  along.

## R5 – The empty My favorite authors page

- **Decision**: replace the sentence with:
  - "You haven't chosen any favorite authors yet."
  - "Choose the star next to an author's name on a book page, or Add to my favorite
    authors on an author's page."
  - a link, "Browse the Catalog" (`/catalog`).

  The page with favorites is unchanged.

## R6 – Layout

- **Star button**:
  - It's inline after the name, at least 44 × 44 CSS px. It uses the existing
    `.inline-form` and a new `.star-button` class: a transparent background and
    `min-width` / `min-height` of 2.75rem.
  - On a phone, a byline with several authors wraps between author-and-star pairs, never
    between a name and its star: each pair is an inline-block (`white-space: nowrap` on
    the pair).
- **Offer**: it uses the existing `.notice` style and the default button.
- **Checks**: the a11y suite checks all three at the spec 003 widths (AC-14).
