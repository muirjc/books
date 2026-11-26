# UI contract: Catalog page (spec 010)

This adds a row to [spec 001 ui-routes.md](../../001-family-reading-list/contracts/ui-routes.md)
and amends the main navigation. The JSON API doesn't change.

| Route | Behaviour |
|---|---|
| All member pages | The main navigation lists My books, Add a book, **Catalog**, Upcoming, Import from Open Library (and Accounts for an admin). **Catalog** has `aria-current="page"` on the Catalog page. |
| `GET /catalog` | `<h1>Catalog</h1>` and a search form (`role="search"`, "Search the catalog"). The form has **Search the catalog** (`q`, up to 200 characters), **Sort by** (`sort`: `title`, `-title`, `author`, `series`, `-added`), a **Not on my list** checkbox (`not_mine=1`), **Apply**, and **Clear** when something is set. Then `#catalog-list`: the count ("N books in the family catalog" / "N books match"), then `ul.catalog-list` rows. Each row has the title (a link to `/catalog/books/{id}/edit`), the authors, the series and number (a link to `/series/{series_id}`), "Coming <date>" while the book isn't out, then **On my list** (a link to `/entries/{entry_id}`) or **Add to my list** (a link to `/books/add?book={id}`, named "Add “Title” to my list"). 50 per page, with **Previous**, "Page n of m" and **Next** links that keep `q`, `sort` and `not_mine`. Empty catalog: "The family catalog is empty." plus a link to Add a book. No match: "No catalog books match." plus a link to `/catalog`. Signed out: 303 to sign in. |
| `GET /catalog` with `HX-Request` | Just the `#catalog-list` contents. |

Unknown or invalid parameters fall back to the defaults: `sort=title`, page 1, and the
filter off. A page past the end shows the last page.

*Amended 2026-11-26 by [spec 018](../../018-navigation-model/contracts/ui-navigation.md): a Books | Series switch sits under the heading; `GET /catalog/series` is the Series view.*
