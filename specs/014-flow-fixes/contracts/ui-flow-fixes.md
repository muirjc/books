# UI contract: Flow Fixes (spec 014)

## Changed routes

| Method | Path | Change |
|---|---|---|
| GET | `/entries/{id}` | Always a Stories section with **Add a story** (`/catalog/books/{book}/stories/add?from=entry:{id}`). Adds a "Jump to" list. The `msg=stories_not_added` text changes. |
| GET | `/books/add` | Also takes `anthology=yes` (box ticked) and `author=<id>` (that author chosen). |
| GET/POST | `/catalog/books/{id}/stories/add` | `from=entry:<id>` sets the return target. `then=another` redirects to a fresh form with `added=<story id>`. |
| GET | `/catalog/stories/{id}/edit` | `from=book:<id>` sets the back link. |
| GET | `/catalog/books/{id}/edit` | Back link to my entry, or to the Catalog. Adds a Jump to Stories link and the new hint. |
| GET | `/catalog/books/{id}/summary` | Back link to my entry, or to Edit book. |
| GET | `/catalog/series/{id}/edit` | Link "View the series". |
| GET | `/series/{id}` | An Add #next row; an **Add a collection with stories in this series** link (`/books/add?series={id}&anthology=yes&from_series={id}`). |
| GET | `/authors/{id}` | **Add a book by this author** (`/books/add?author={id}`). |
| POST | `/import/authors/{key}` | The Books added page links to the Catalog. |
| POST | `/admin/users/{id}` | `action=deactivate` or `make_admin` without `confirm=yes` renders the confirmation (200, no change). |
| POST | `/admin/users/{id}/reset-password` | A valid password without `confirm=yes` renders the confirmation (200, no change; the password is in a hidden field only). |

## Every page

- **Navigation:** `aria-current="page"` is on the related tab (research R4). The import tab
  reads **Import**.
- **Account area:** **Change password** → `/account/password`.

## Return targets

Return targets come from ids only. A `from` that is malformed, another member's, or for a
different book is ignored.
