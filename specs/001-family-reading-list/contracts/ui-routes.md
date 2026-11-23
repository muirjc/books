# UI Routes: Family Reading List

Server-rendered pages (Jinja2 + HTMX). These pages are not part of the OpenAPI contract
(Constitution Principle VII). Their form and query input is validated by the same Pydantic
models as the JSON API, and they call the same services.

Page layout at phone, tablet and laptop widths is fixed by
[spec 003's layout contract](../../003-responsive-layout/contracts/ui-layout.md).

Every POST carries the CSRF token: a hidden `csrf_token` field, or the `X-CSRF-Token`
header that HTMX sends from `hx-headers` on `<body>`. HTMX requests (with the `HX-Request`
header) get an HTML fragment back; other requests get a full page or a redirect
(POST → 303 → GET).

| Method | Path | Purpose | Spec |
|---|---|---|---|
| GET | `/sign-in` | Sign-in form; lists recently used profiles on this device | FR-001, FR-007 |
| POST | `/sign-in` | Sign in; 303 to `/`, or to `/account/password` if a change is required | FR-001, FR-027 |
| POST | `/sign-out` | Sign out; 303 to `/sign-in` | FR-001 |
| POST | `/switch-user` | Sign out, keep the recent profiles; 303 to `/sign-in` | FR-007 |
| GET, POST | `/account/password` | Change own password (forced after reset) | FR-004, FR-028 |
| GET | `/` | My list: search, sort, filter, paging (fragment: `#reading-list`); `?upcoming=1` and the Now out notice ([spec 007](../../007-upcoming-books/contracts/ui-upcoming.md)); a link to authors with no books when there are any ([spec 008](../../008-delete-unused-authors/contracts/ui-delete-author.md)) | FR-021, FR-023 |
| GET | `/books/add` | Add-book form with type-ahead; `?after=<own entry id>` pre-fills the next book ([spec 004](../../004-save-and-add-another/contracts/ui-add-another.md)); `?book=`, `?series=&number=` and `?from_series=` start from a series page ([spec 006](../../006-series-viewer/contracts/ui-series-viewer.md)); a Release date field, Pre-ordered, and Coming on a chosen book ([spec 007](../../007-upcoming-books/contracts/ui-upcoming.md)) | FR-016 |
| POST | `/books/add` | Add to my list (existing or new book); `then=another` redirects to the next-book form ([spec 004](../../004-save-and-add-another/contracts/ui-add-another.md)) New author and series names are confirmed first ([spec 005](../../005-confirm-new-names/contracts/ui-new-names.md)). With `from_series`, a successful save returns to that series page ([spec 006](../../006-series-viewer/contracts/ui-series-viewer.md)). | FR-016, FR-017 |
| GET | `/suggest/books?q=` | Type-ahead fragment; a book found by one of its stories' titles says "contains “…”" ([spec 009](../../009-collection-stories/contracts/ui-stories.md)) | FR-010 |
| GET | `/suggest/authors?q=` | Type-ahead fragment; matches real name | FR-010 |
| GET | `/suggest/series?q=` | Type-ahead fragment | FR-010 |
| GET | `/suggest/stories?q=` | Story type-ahead fragment for Add a story ([spec 009](../../009-collection-stories/contracts/ui-stories.md)) | spec 009 |
| GET | `/entries/{id}` | My entry, with book details and summary; 404 if not mine. Coming / Released and Pre-ordered ([spec 007](../../007-upcoming-books/contracts/ui-upcoming.md)); the book's stories ([spec 009](../../009-collection-stories/contracts/ui-stories.md)) | FR-020 |
| POST | `/entries/{id}` | Update status, date, times read, notes; and, when the form sends a title, the book's title, authors, series, number, ISBN and release date (family-wide; skipped if unchanged). Nothing saves if any field is refused (books-4l5) New author and series names are confirmed first ([spec 005](../../005-confirm-new-names/contracts/ui-new-names.md)). Pre-ordered ([spec 007](../../007-upcoming-books/contracts/ui-upcoming.md)). Book fields left as the page first showed them keep the book's current values, so a page opened before another member's edit never writes old values back (books-mbx). | FR-009, FR-018, FR-029 |
| POST | `/entries/{id}/read-again` | Start a re-read | FR-029 |
| POST | `/entries/{id}/remove` | Remove from my list (asks to confirm first) | FR-019 |
| GET | `/upcoming` | My books not out yet, then other upcoming catalog books with Add to my list ([spec 007](../../007-upcoming-books/contracts/ui-upcoming.md)) | spec 007 |
| GET | `/series/{id}` | Every catalog book in this series, in order, with my own status, gaps and Add links ([spec 006](../../006-series-viewer/contracts/ui-series-viewer.md)); Coming and Pre-ordered labels ([spec 007](../../007-upcoming-books/contracts/ui-upcoming.md)); stories at their numbers, with the books they're in and my status from my own entries ([spec 009](../../009-collection-stories/contracts/ui-stories.md)) | FR-022 |
| GET | `/catalog` | Every catalog book, 50 per page. Searched by title, author, real name, series, story or ISBN; sorted; filtered to books not on my list. Each book shows On my list (my entry) or Add to my list. Linked from the main navigation as **Catalog** ([spec 010](../../010-catalog-page/contracts/ui-catalog.md)) | spec 010 |
| GET, POST | `/catalog/books/{id}/edit` | Edit a catalog book, including its release date ([spec 007](../../007-upcoming-books/contracts/ui-upcoming.md)). New author and series names are confirmed first ([spec 005](../../005-confirm-new-names/contracts/ui-new-names.md)). Book fields left as the page first showed them keep the book's current values, so a page opened before another member's edit never writes old values back (books-mbx). Lists the book's stories, with Add, Edit and Remove ([spec 009](../../009-collection-stories/contracts/ui-stories.md)). | FR-009 |
| GET, POST | `/catalog/authors/{id}/edit` | Edit an author, pen name, real name; lists the books that list the author, and offers Delete author when there are none ([spec 008](../../008-delete-unused-authors/contracts/ui-delete-author.md)); its stories count too ([spec 009](../../009-collection-stories/contracts/ui-stories.md)) | FR-009, FR-014 |
| GET | `/catalog/authors/unused` | Authors no book lists ([spec 008](../../008-delete-unused-authors/contracts/ui-delete-author.md)) | spec 008 |
| POST | `/catalog/authors/{id}/delete` | Asks first; with `confirm=yes` deletes an author no book lists, else 409 ([spec 008](../../008-delete-unused-authors/contracts/ui-delete-author.md)) | spec 008 |
| GET, POST | `/catalog/series/{id}/edit` | Rename a series; lists every catalog book in it (number, link to edit), including books on nobody's list (books-cay). A "number taken" conflict anywhere links to the book holding the number | FR-009 |
| GET, POST | `/catalog/books/{id}/stories/add` | Add a new or existing story to a book ([spec 009](../../009-collection-stories/contracts/ui-stories.md)) | spec 009 |
| GET, POST | `/catalog/stories/{id}/edit` | Edit a story; lists the books it's in ([spec 009](../../009-collection-stories/contracts/ui-stories.md)) | spec 009 |
| POST | `/catalog/books/{id}/stories/{story_id}/remove` | Asks first; with `confirm=yes` takes the story out of the book, deleting it when no other book has it ([spec 009](../../009-collection-stories/contracts/ui-stories.md)) | spec 009 |
| GET, POST | `/catalog/books/{id}/summary` | Write a new summary; shows history | FR-024 |
| GET | `/admin/users` | Accounts list (Admin only) | FR-003 |
| GET, POST | `/admin/users/new` | Create an account | FR-003 |
| POST | `/admin/users/{id}` | Change display name, role, active state | FR-004, FR-005 |
| POST | `/admin/users/{id}/reset-password` | Set a temporary password | FR-004 |

Route rules:

- Every route except `/sign-in` requires a session. Without one, the request gets a 303 to
  `/sign-in` (or `HX-Redirect` for HTMX).
- While `must_change_password` is set, every route except `/account/password` and
  `/sign-out` redirects to `/account/password`.
- `/admin/*` returns 403 for non-Admins. No admin route shows reading entries (AC-14).
- There is no route for creating an account without signing in (AC-12).
