# Research: Import an Author's Books

Phase 0 decisions for [plan.md](plan.md). Numbered R1–R16 for reference from tasks and
code. Sources checked 2026-11-19.

## R1. Book-data source: Open Library only (decision books-zl3)

- **Decision**: Open Library is the only source for this feature. Google Books is not used.
  There is no Admin setting to choose sites.
- **Rationale**: the maintainer first chose both sites with an Admin switch. Google's
  [branding guidelines](https://developers.google.com/books/branding) say results from the
  Google Books API "may not be reordered or otherwise altered" and need a "Powered by Google"
  badge beside them. The spec combines, de-duplicates, sorts and filters results (FR-004 to
  FR-006), which would alter Google's results. The maintainer chose Open Library only, and
  the decision is recorded as bead books-zl3.
- **Future**: Google Books may be needed later, for example for AI summary drafts or to fill
  gaps such as ISBNs and series, in a design that shows its results unaltered with the badge
  (follow-up bead books-395). Open Library sits behind a source-adapter interface (R4), so a
  second adapter changes no other layer. Re-read Google's terms before starting that work.
- **Alternatives considered**: (a) a separate, unaltered Google Books section, with sorting,
  filtering and de-duplication for Open Library only: more screens and rules for little gain;
  (b) Google Books used behind the scenes to fill gaps: storing Google data in the catalog is a
  grey area under its terms.

## R2. Open Library terms and limits

- **Decision**: use the public JSON API with a `User-Agent` that names the app; keep to at most
  1 request a second overall: each of the two app processes spaces its requests at least 2 s
  apart. Never bulk-download.
- **Rationale**: the [developer page](https://openlibrary.org/developers/api) gives about 1
  request a second to unidentified clients and about 3 a second to clients that send a
  `User-Agent` with an app name and contact email. It asks for the data dumps, not the API, for
  bulk downloads. One import needs one to three requests (R3), so 1 a second overall is ample.
- **User-Agent**: exactly `FamilyBookTracker/<version>`. No contact address is sent: the person
  running the app would usually supply their own email, and Principle IX forbids requests that
  identify a family member. Open Library therefore treats the app as unidentified, so the
  rate stays within its limit of about 1 request a second.
- **Alternatives considered**: no `User-Agent` (Open Library asks for one); an optional contact
  address set by the operator (rejected: in practice a parent's address, which identifies a
  family member; /speckit-analyze finding C1); a hard-coded project contact (sends an
  identity the operator didn't choose).

## R3. Open Library endpoints and fields

Checked with live requests on 2026-11-19 (author "Brandon Sanderson").

- **Author search**: `GET /search/authors.json?q=<name>&limit=10` returns `key` (e.g.
  `OL1394865A`), `name`, `birth_date`, `death_date`, `top_work` and `work_count`: exactly the
  distinguishing details FR-002 needs. "Brandon Sanderson" returns two authors (238 and 14
  works), so the chooser (AC-08) is needed even for well-known names.
- **Author's works**: `GET /search.json?author_key=<key>&fields=key,title,first_publish_year,
  author_name,author_key,isbn,edition_count&limit=1000&page=<n>`. With `limit=1000`, all 239
  works came back in one response (83 kB, 1.1 s). Asking only for the fields needed is what
  Open Library [asks of API users](https://blog.openlibrary.org/2025/01/16/api-search-json-performance-tuning/).
- **Paging and cap**: request up to two pages of 1,000 and stop; `numFound` gives the total for
  the "showing the first 2,000 of N" note (FR-020).
- **Series**: search returns no series fields. The work record (`/works/<id>.json`) has none
  either. Series appear only on some editions, as free text, often translated (for example
  "Mistborn", "The Mistborn Saga", "Fills de la boira") and without a number. Fetching editions
  for every work would take about 80 s for a 239-work author at the rate limit. **Series are
  not imported** (spec FR-010).
- **ISBNs**: `isbn` lists every edition's ISBNs (ISBN-10 and ISBN-13, many languages). No single
  one is the family's copy, so **none is stored** (FR-011); they are converted to ISBN-13 and
  used only for matching (R6).
- **Alternatives considered**: `/authors/<key>/works.json` (no first published year, no ISBNs;
  50 a page); per-work edition look-ups for series (too slow, ambiguous).

## R4. Source-adapter interface

- **Decision**: `sources/base.py` defines a `BookSource` protocol with two async methods,
  `search_authors(name) -> list[AuthorCandidate]` and
  `author_works(author_id) -> WorkList` (works plus the total). `AuthorCandidate`,
  `WorkCandidate` and `WorkList` are frozen dataclasses in `domain/`. Failures raise
  `SourceUnavailable`. `sources/open_library.py` implements it with `httpx.AsyncClient`;
  `tests/fakes.py` provides `FakeBookSource` for service tests.
- **Rationale**: Principle IV requires an adapter interface; the planned AI summary feature and
  any later Google Books adapter (books-395) plug into the same place. Services never see HTTP.
- **Alternatives considered**: calling httpx from the service (untestable without HTTP fakes,
  and breaks Principle IV).

## R5. Caching lookups (FR-017)

- **Decision**: a `source_lookup_cache` table in the existing PostgreSQL database, keyed by
  source, kind (`author_search` or `author_works`) and lookup key (the normalized name, or the
  Open Library author key), holding the parsed result as JSONB with `fetched_at` and
  `expires_at` (24 hours). Expired rows are deleted whenever a new row is written.
- **Rationale**: Principle III requires source lookups to be cached outside the catalog. Two
  app processes share it, and it survives restarts. A table is not a new datastore
  (Principle VIII). It also holds the draft list between "show" and "confirm" (R8).
- **Alternatives considered**: in-process memory (not shared between the two workers, lost on
  restart); Redis (a new datastore, forbidden without an amendment).

## R6. Matching works to the catalog (FR-004, FR-005)

- **Normalized title**: lower case, Unicode NFKC, punctuation removed, whitespace collapsed,
  a leading "the", "a" or "an" dropped. **Normalized name**: lower case, NFKC, whitespace
  collapsed.
- **Duplicates within Open Library's list** (AC-12): works with the same normalized title and
  normalized first author are merged into one. The merged entry keeps the work with the most
  editions as its identifier, the earliest first published year, and the union of ISBNs.
- **Already in the catalog** (AC-04, AC-15), checked in this order: a `book_source_ref` with the
  work's Open Library id; any catalog `isbn_13` among the work's ISBNs (ISBN-10s converted to
  ISBN-13); or a catalog book whose first author's name equals the work's first author
  (normalized) and whose normalized title is equal. The last check runs in Python over the
  catalog books by that author: at most a few hundred rows for one family.
- **Already on my list** (AC-17): for the matched catalog book ids, one query through
  `ReadingEntryRepository.book_ids_on_list(ids)`, which is bound to the session user (R10).
- **Alternatives considered**: a database index on a normalized title (no DB uniqueness on
  titles exists in spec 001, because different books may share a title); fuzzy matching
  (false merges are worse than an occasional duplicate the family can see and fix).

## R7. Importing on confirm (FR-007 to FR-013)

- **Decision**: one transaction per confirm. For each selected work, inside a savepoint:
  find or create each author (reusing `catalog_service.create_author`; an `author_exists`
  conflict means "use the existing one"), create the book with `created_by` = the importer,
  then insert its `book_source_ref`. Then add the reading entry through
  `ReadingEntryRepository` with the chosen status, skipping books already on the list.
- **Concurrency** (AC-16): `book_source_ref` is unique on (`source`, `source_work_id`). If two
  members import the same new work at once, the second insert fails, its savepoint rolls back
  (removing its just-created book), and the existing book is used instead. Authors already rely
  on the case-insensitive unique index from spec 001 (research R9 there).
- **Status**: one status for the whole selection; `times_read` comes from the existing
  `apply_status_change` rule, so Finished gives 1 and the others 0.
- **Alternatives considered**: one transaction per book (a failure half-way leaves a partial
  import with no summary); advisory locks (the unique constraint is simpler and is enforced by
  the database, Principle VI).

## R8. Draft state between listing and confirming

- **Decision**: the confirm request sends only the Open Library author key, the selected work
  ids and the status. The server reads the works from the cached `author_works` row. If that row
  has expired, the confirm is refused with `results_expired` and the member reloads the list.
  A work id that isn't in the cached list is a validation error.
- **Rationale**: titles and authors come from the server's own copy of Open Library's answer,
  not from the browser, so provenance (FR-009) can't be forged. Nothing is fetched at confirm
  time, matching the spec's edge case.
- **Alternatives considered**: posting full book data from the browser (provenance could be
  faked); re-fetching at confirm (slower, and the list could change under the member).

## R9. Timeouts, errors and rate limiting (FR-016, FR-018)

- **Decision**: each Open Library call is wrapped in `asyncio.timeout(10)` on top of httpx's own
  connect and read timeouts. Timeouts, connection errors, 5xx and 429 responses all raise
  `SourceUnavailable`; the API returns `503` with `code=source_unavailable`, and the page shows
  the spec's message (AC-13). A per-process async limiter spaces requests at least 2 s apart
  (R2). Time spent waiting for it counts against the same 10 s: if the wait would end after
  the deadline, the call fails at once with `SourceUnavailable`.
  Malformed JSON or missing fields in a single work drop that work only, with a log line.
- **Logging**: kind, HTTP status and duration only; never the session user (Principle IX).

## R10. Ownership and authorization (Principle I)

- **Decision**: import endpoints take the user only from the session (`current_user`). The
  works list and the confirm both use `ReadingEntryRepository(db, user.id)`. The new method
  `book_ids_on_list` follows the repository's rule of never taking a user id from its caller.
  No Admin-only endpoint is added (FR-014).
- **Cross-user tests**: Alice imports; Ben's list is unchanged and his works list doesn't show
  Alice's books as "on my list" (AC-18).

## R11. JSON API shape (Principle VII)

- `GET /api/v1/import/authors?q=` → author candidates.
- `GET /api/v1/import/authors/{author_key}/works?sort=&q=` → the de-duplicated works with their
  catalog and list state, sorted and filtered server-side.
- `POST /api/v1/me/imports` → adds the selection to my list; `201` with the summary.
  Under `/me` because it writes personal entries (as `/me/readings` does).
- Details in [contracts/openapi.yaml](contracts/openapi.yaml). All three are additions, so the
  breaking-change check passes.

## R12. Server-rendered flow without custom JavaScript (FR-006, FR-019)

- **Decision**: three pages: search (`/import`), author choice (`/import/authors?q=`, which
  goes straight to the works page when there's exactly one match) and works
  (`/import/authors/{key}`). Sorting and the title filter re-render the works table through
  HTMX, with `hx-include` carrying the ticked boxes so ticks survive. "Select all shown" is an
  HTMX request that re-renders with every shown, selectable work ticked. No custom script, only
  the vendored HTMX already used by spec 001.
- **Confirm**: `POST /import/authors/{key}` renders the summary page directly (200) rather than
  POST → 303 → GET. There is no flash-message store, and a repeated submit is harmless, since
  books already on the list are skipped.
- **Accessibility**: a real `<table>` with a checkbox and visible label per row, a caption with
  counts, the status as a `<fieldset>` of radio buttons, and an `aria-live="polite"` region for
  "N selected" and the result. These are covered by the existing axe-core and keyboard tests.

## R13. Provenance (FR-009, AC-07)

- **Decision**: `book_source_ref` (book, source, source work id, imported by, imported at). The
  book's own `created_by` and `created_at` are set to the importer and the time, so spec 001's
  "who edited and when" shows the import with no change there. The book page shows "Imported
  from Open Library" with a link to the work.
- **Alternatives considered**: columns on `book` (a second source later would need a second set
  of columns).

## R14. Recorded HTTP fixtures (Principle V, External layer)

- **Decision**: `tests/external/fixtures/open_library/` holds JSON responses captured once from
  the live API, trimmed to the requested fields. Tests replay them with `httpx.MockTransport`.
  `scripts/record_open_library_fixtures.py` re-captures them by hand when Open Library's format
  changes; CI never calls Open Library. Fixtures cover: a single match, several matches, no
  match, a 239-work list, a list with duplicate works, a list over 2,000, a 503, a timeout, and
  malformed data.
- **Alternatives considered**: respx or vcrpy (new dependencies; `MockTransport` ships with
  httpx).

## R15. Performance (SC-002)

- **Decision**: a `perf` test lists 300 works for an author against the 5,000-book seed with the
  cache warm, and requires p95 under 1 s. The uncached 5 s target depends mostly on Open Library
  (about 1.1 s measured); a unit test checks the 10 s timeout path instead of a live timing.

## R16. Deployment

- **Decision**: no infrastructure change. The app container is on the Compose `edge` network,
  which has outbound internet; the Pi's ufw allows outgoing traffic. Product spec section 10
  already says features after 001 need outbound HTTPS. No new setting is needed;
  `deploy/pi/.env.example` gets a comment saying the app now calls `openlibrary.org`.
