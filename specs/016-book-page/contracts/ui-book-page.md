# UI contract: Read-only book page (spec 016)

## New route

| Method | Path | Result |
|---|---|---|
| GET | `/books/{book_id}` | 200, the book page. 404 for an unknown book; 422 for an invalid id; redirect to sign-in when signed out. Reads `wanted` / `already` (spec 015 notice) and `msg=story_added` / `story_already`. |

## The page, top to bottom

1. `<h1 id="book-<id>">` with the title.
2. Authors (links to `/authors/<id>`), series and number (link to `/series/<id>`), release
   information, and the source reference.
3. My status: the badge (link to `/entries/<id>`) with any finished date, plus **Open my
   entry**. Otherwise "Not on my list", **Want to read** (`back=/books/<id>`) and **Add
   with details…** (`/books/add?book=<id>`).
4. The quick-add notice, when there is one.
5. Summary: the text and "Written by …", or "No summary yet."; **Write a summary** and
   **Draft with AI**.
6. Stories in this book (`id="stories-heading"`): "#n Series — Title · Also in “X”", or "No
   stories recorded", plus **Add a story** (`?from=page`).
7. More: **Edit book**, all books by each author, the series page.

## Changed

| Where | Change |
|---|---|
| `book_row` (Catalog, author pages, Upcoming) | The title links to `/books/<id>` |
| `/series/{id}` | Book titles and story rows' containing books link to `/books/<id>` |
| `/catalog/authors/{id}/edit`, `/catalog/series/{id}/edit` | Book titles link to `/books/<id>` |
| `/entries/{id}`, `/catalog/books/{id}/edit` | Gain a "View the book page" link |
| `POST /books/{id}/want-to-read` | `back` may be `/books/<uuid>` |
| `/catalog/books/{id}/stories/add` | `from=page` returns to the book page |
| My books (`/`) | Unchanged: titles open my entry |
