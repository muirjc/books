# UI Routes: Import an Author's Books

Server-rendered pages added by spec 002, following the rules in
[001 ui-routes.md](../../001-family-reading-list/contracts/ui-routes.md): every route needs a
session, forced password changes redirect first, POSTs carry the CSRF token, and HTMX
requests get a fragment. Form and query input goes through the same Pydantic models as the
JSON API ([openapi.yaml](openapi.yaml)) and the same services (Constitution Principle VII).
No custom JavaScript (research R12).

| Method | Path | Purpose | Spec |
|---|---|---|---|
| GET | `/import` | Search form: author name. Linked from "Add a book" and the main navigation | FR-001 |
| GET | `/import/authors?q=` | Matching authors with birth/death years, best-known title and number of works; with exactly one match, 303 (or `HX-Redirect`) to its works page; with none, "No author found" and a link to `/books/add` | FR-002, AC-08, AC-09 |
| GET | `/import/authors/{author_key}` | The works table: title, year, co-authors, state badge ("Already on your list", "In the family catalog"), checkbox (none for books on my list), a status select (default Finished), "Apply sort and filter" (the form's default button, so Enter in the filter box never ticks anything) and "Select all shown". `?expired=1` adds a note that the list was fetched again. Unknown key: "No such author on Open Library" (404) | FR-003 to FR-006, FR-020, AC-23 |
| POST | `/import/authors/{author_key}/view` | Read-only re-render of fragment `#import-works` for sort, title filter and "Select all shown" (`select=shown`, at most 500 ticked), with the ticked `work` values in the body (research R12). Ticked works the filter hides are kept as hidden `work` fields, so they are still sent on confirm; a tick that is no longer in the list is dropped, and a merged id becomes the work it was merged into. Because HTMX ignores error responses, an HTMX request that fails (bad form value, Open Library unreachable) gets `HX-Redirect` to the works page instead. CSRF-checked like every POST; blank `sort` or `q` means absent | FR-006, AC-10, AC-11 |
| POST | `/import/authors/{author_key}` | Confirm: add the ticked works (at most 500) to my list with the chosen status; renders the summary (200), not a redirect (research R12). `status` and each `work` are validated with Pydantic; a bad value or a refused confirm redisplays the table from the cache with the ticks kept (422), and never calls Open Library, because the confirm may hold the import lock | FR-007 to FR-014, FR-021 |

States and messages:

- **Open Library unreachable while the cached list still has under an hour left**: the cached
  list is shown; it is fetched again on a later visit.
- **Open Library unreachable**: the search or works page shows "The book site couldn't be
  reached. Try again later, or add the book by hand," with a link to `/books/add` (AC-13).
- **Results expired** at confirm: nothing is added; the page sends the member (303, or
  `HX-Redirect`) to `/import/authors/{author_key}?expired=1`, which fetches the list again
  outside the import lock and says "The list had expired, so it was fetched again from Open
  Library. Tick your books again." The JSON API still answers 409 `results_expired`.
- **Nothing ticked**: the confirm is refused with a field error on the table.
- **More than 500 ticked**: "You can add up to 500 books at a time." Nothing is added (AC-21).
- **Who added it**: like every catalog book, an imported book shows "Last edited by <name>";
  nothing on these pages shows another member's status, dates or notes (research R17).
- **Summary**: "Added N books to your list (M new to the family catalog)", a list of the books
  linking to their entries, and any skips: "Already on your list", or "Same book as another one you ticked" (FR-012,
  FR-021). Announced through an
  `aria-live="polite"` region.
- **Book page** (`/entries/{id}` and the catalog book edit page): an imported book shows
  "Imported from Open Library" with a link to `https://openlibrary.org/works/<id>` (FR-009).
