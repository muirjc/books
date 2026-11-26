# UI contract: Author page and favorite authors (spec 011)

This adds rows to [spec 001 ui-routes.md](../../001-family-reading-list/contracts/ui-routes.md)
and amends `/`, `/catalog`, `/upcoming`, `/series/{id}`, `/entries/{id}`,
`/catalog/books/{id}/edit`, `/catalog/authors/{id}/edit` and `/catalog/authors/unused`.
Every POST needs the session CSRF token.

| Route | Behaviour |
|---|---|
| `GET /authors/{id}` | The page holds: <ul><li>`<h1>` with the author's name, and "Pen name of …" or "Pen name" when it applies;</li><li>**Edit author** (`/catalog/authors/{id}/edit`);</li><li>the favorite status ("★ One of your favorite authors") and a form button: **Add to my favorite authors** or **Remove from my favorite authors**;</li><li>a link to **My favorite authors**;</li><li>`<h2>Books</h2>`, then `<h3>` per series (linking to `/series/{sid}`) and `<h3>Other books</h3>`. Each group is a `ul.catalog-list` of rows: the title (to Edit book), "#n" when numbered, "Coming <date>", then my status badge with **On my list** (to `/entries/{eid}`), or **Add to my list** (`/books/add?book={bid}`, named with the title);</li><li>`<h2>Stories</h2>` when there are any;</li><li>with no books, "No book in the family catalog lists this author."</li></ul>`?msg=favorited` shows "Added to your favorite authors." and `?msg=unfavorited` shows "Removed from your favorite authors." An unknown id returns 404. |
| `POST /authors/{id}/favorite` | `favorite=yes` adds and `favorite=no` removes, then 303 to `/authors/{id}?msg=favorited` or `msg=unfavorited`. Any other value returns 422. An unknown or deleted author returns 404. |
| `GET /authors/favorites` | `<h1>My favorite authors</h1>`, then a list of author links by sort name. With none: "You haven't chosen any favorite authors yet." and how to choose one, with a **Browse the Catalog** link ([spec 017](../../017-favorite-author-shortcuts/contracts/ui-favorites.md) AC-06). |
| `GET /` | The Author filter gains **My favorite authors** (`author_id=favorites`). The page links to **My favorite authors** below the list. |
| Book rows on `/`, `/catalog`, `/upcoming`, `/series/{id}` | Each author's name links to `/authors/{id}`. |
| `/entries/{id}`, `/catalog/books/{id}/edit` | The authors list gives each author a link to their page, next to the existing **Edit author** link. |
| `GET /catalog/authors/{id}/edit` | With no books or stories, but favorited: by me, "This author is one of your favorite authors. Remove them from your favorites to delete them." with a link to the Author page; by another member only, "A family member has this author as a favorite, so they can't be deleted." No Delete button in either case. Edit author also links to the Author page. |
| `POST /catalog/authors/{id}/delete` | When favorited (including meanwhile), shows Edit author with the message above (409). Nothing is deleted. |
| `GET /catalog/authors/unused` | Leaves out favorited authors, as does its count on My books. |

*Amended 2026-11-26 by [spec 018](../../018-navigation-model/contracts/ui-navigation.md): `GET /authors/favorites` redirects to `/authors?favorites=1`, the Authors page with Favorites only. The author page's My favorite authors link points there, and the menu's Authors item is current on author pages.*
