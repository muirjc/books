# UI contract: Upcoming books (spec 007)

Amends the `/`, `/series/{id}`, `/entries/{id}`, `/books/add` and
`/catalog/books/{id}/edit` rows of
[spec 001 ui-routes.md](../../001-family-reading-list/contracts/ui-routes.md), and adds
`/upcoming`.

## `GET /upcoming` (new)

`200`, signed-in members only (sign-in redirect as other pages).

| Section | Contents |
|---|---|
| `<h1>Upcoming</h1>` | |
| `<h2>On my list</h2>` | my entries with `release_date > today`, soonest first: title (links to `/entries/<id>`), authors, series, "Coming <date>", status, "Pre-ordered" |
| `<h2>Also coming in the family catalog</h2>` | catalog books with `release_date > today` not on my list, soonest first: title, authors, series, "Coming <date>", **Add to my list** → `/books/add?book=<id>` |
| Empty | "Nothing on your list is coming up." / "Nothing else in the family catalog is coming up.", plus **Add a book** |

Navigation: "Upcoming" after "Add a book", `aria-current="page"` on this page.

## `GET /` (My books)

| Addition | Behaviour |
|---|---|
| `?upcoming=1` | only my books with `release_date > today`, soonest first, ties by title; `sort` ignored; kept in paging links; counts as a filter (Clear shows) |
| Filter form | checkbox "Upcoming only" (`name=upcoming value=1`), hint "Soonest first" |
| Now out notice | full page only (not the HTMX partial), before the filters: `<div class="notice" role="status" id="now-out">` "Now out:" then a list of links to `/entries/<id>` with "(pre-ordered)"; absent when nothing qualifies |
| Rows | "Coming <date>" and "Pre-ordered" (R9) in `.book-release` |

## `GET /series/{id}`

Book rows: the status text gains " · Coming <date>" (and " · Pre-ordered" for my entry)
while the book is upcoming.

## `GET /entries/{id}`

- **Heading area:** "Coming <date>" (upcoming) or "Released <date>" (past), plus
  "Pre-ordered" (R9).
- **Book fields:** gain Release date.
- **Entry fields:** gain the Pre-ordered checkbox.
- **POST:** saves both. Release date goes through `save_book_details`, as other book
  fields do.

## `GET, POST /books/add` and `/catalog/books/{id}/edit`

- **Book fields:** gain "Release date (optional)" (`type=date`).
- **Entry fields on Add a book:** gain "Pre-ordered".
- **Invalid date:** `422` with the error on `release_date`.
- **The chosen-book display (spec 006):** gains "Coming <date>".
- **Add and add another:** clears both fields.

*Amended 2026-11-26 by [spec 018](../../018-navigation-model/contracts/ui-navigation.md): My books no longer has the Upcoming only filter (`?upcoming=1` redirects to `/upcoming`) or the Now out box. Now out is the first section of the Upcoming page (`#now-out`), and My books shows one line linking to it. The JSON API's `upcoming` filter is unchanged.*
