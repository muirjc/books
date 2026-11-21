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
| GET | `/` | My list: search, sort, filter, paging (fragment: `#reading-list`) | FR-021, FR-023 |
| GET | `/books/add` | Add-book form with type-ahead; `?after=<own entry id>` pre-fills the next book ([spec 004](../../004-save-and-add-another/contracts/ui-add-another.md)) | FR-016 |
| POST | `/books/add` | Add to my list (existing or new book); `then=another` redirects to the next-book form ([spec 004](../../004-save-and-add-another/contracts/ui-add-another.md)) | FR-016, FR-017 |
| GET | `/suggest/books?q=` | Type-ahead fragment | FR-010 |
| GET | `/suggest/authors?q=` | Type-ahead fragment; matches real name | FR-010 |
| GET | `/suggest/series?q=` | Type-ahead fragment | FR-010 |
| GET | `/entries/{id}` | My entry, with book details and summary; 404 if not mine | FR-020 |
| POST | `/entries/{id}` | Update status, date, times read, notes; and, when the form sends a title, the book's title, authors, series, number and ISBN (family-wide; skipped if unchanged). Nothing saves if any field is refused (books-4l5) | FR-009, FR-018, FR-029 |
| POST | `/entries/{id}/read-again` | Start a re-read | FR-029 |
| POST | `/entries/{id}/remove` | Remove from my list (asks to confirm first) | FR-019 |
| GET | `/series/{id}` | My books in this series, in order | FR-022 |
| GET, POST | `/catalog/books/{id}/edit` | Edit a catalog book | FR-009 |
| GET, POST | `/catalog/authors/{id}/edit` | Edit an author, pen name, real name | FR-009, FR-014 |
| GET, POST | `/catalog/series/{id}/edit` | Rename a series; lists every catalog book in it (number, link to edit), including books on nobody's list (books-cay). A "number taken" conflict anywhere links to the book holding the number | FR-009 |
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
