# UI contract: Consistent rows and quick Want to read (spec 015)

## New route

| Method | Path | Form | Result |
|---|---|---|---|
| POST | `/books/{book_id}/want-to-read` | `csrf_token`, `back` | 303 to `back` plus `wanted=<book>` (or `already=<book>`) and `#book-<book>`; 404 for an unknown book; 403 without CSRF |

`back` is allow-listed (research R2). Anything else is `/catalog`.

## Changed pages

| Page | Change |
|---|---|
| `/catalog`, `/authors/{id}`, `/upcoming` | Rows use `book_row` (research R4): my status badge links to my entry; books not on my list get **Want to read** and **Add with details…**. The page reads `wanted` / `already` for the notice. |
| `/series/{id}` | Status as a badge; **Want to read** and **Add with details…** on book rows and on each containing book of a story row; reads `wanted` / `already`. |
