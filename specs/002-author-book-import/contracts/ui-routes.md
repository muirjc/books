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
| GET | `/import/authors/{author_key}?sort=&q=` | The works table: title, year, co-authors, state badge ("Already on your list", "In the family catalog"), checkbox (none for books on my list), status radio buttons (default Finished), "Select all shown". Fragment `#import-works` for sort, filter and select-all; `hx-include` keeps ticked boxes | FR-003 to FR-006, FR-020 |
| POST | `/import/authors/{author_key}` | Confirm: add the ticked works to my list with the chosen status; renders the summary (200), not a redirect (research R12) | FR-007 to FR-013 |

States and messages:

- **Open Library unreachable**: the search or works page shows "The book site couldn't be
  reached. Try again later, or add the book by hand," with a link to `/books/add` (AC-13).
- **Results expired** at confirm: "These results are more than a day old. Reload the list and
  confirm again." Nothing is added.
- **Nothing ticked**: the confirm is refused with a field error on the table.
- **Summary**: "Added N books to your list (M new to the family catalog)", a list of the books
  linking to their entries, and any "Already on your list" skips (FR-012). Announced through an
  `aria-live="polite"` region.
- **Book page** (`/entries/{id}` and the catalog book edit page): an imported book shows
  "Imported from Open Library" with a link to `https://openlibrary.org/works/<id>` (FR-009).
