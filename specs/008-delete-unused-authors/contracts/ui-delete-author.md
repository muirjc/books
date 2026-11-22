# UI contract: Delete an author with no books (spec 008)

Amends the `/` and `/catalog/authors/{id}/edit` rows of
[spec 001 ui-routes.md](../../001-family-reading-list/contracts/ui-routes.md), and adds two
routes.

| Route | Behaviour |
|---|---|
| `GET /` | When any author has no books, a link `<a href="/catalog/authors/unused">Authors with no books (N)</a>` after the list. Full page only, not the HTMX partial. |
| `GET /catalog/authors/unused` | `<h1>Authors with no books</h1>`, then a list by sort name of links to `/catalog/authors/<id>/edit`. Empty: "Every author in the family catalog has at least one book." With `?msg=deleted&author=<name>&sig=<HMAC of the name>`, a status message "Deleted “Name”."; without a valid signature, no message |
| `GET /catalog/authors/{id}/edit` | Adds a "Books" section listing linked books (links to `/catalog/books/<id>/edit`). With books: "This author can't be deleted while books list them. Change those books' authors first." With none: "No book in the family catalog lists this author." and a form `POST /catalog/authors/{id}/delete` with a **Delete author** button. |
| `POST /catalog/authors/{id}/delete` without `confirm=yes` | Books now list the author: `409`, Edit author with "“Name” now has a book, so it can't be deleted." Otherwise `200` confirm page: "Delete “Name” from the family catalog?", a **Delete** button (`confirm=yes`) and a **Cancel** link back to Edit author. |
| `POST /catalog/authors/{id}/delete` with `confirm=yes` | No books: deleted, `303 /catalog/authors/unused?msg=deleted&author=<url-encoded name>&sig=<hmac>`, and the page shows "Deleted “Name”." in a status message. Has books: `409`, Edit author with the error "“Name” now has a book, so it wasn't deleted." Unknown: `404`. |

All POSTs need the session CSRF token. The deleted name is shown only as text, escaped, and
only when its signature (keyed with the app's secret key) checks out.
