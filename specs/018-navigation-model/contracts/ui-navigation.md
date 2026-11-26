# UI contract: Consistent navigation (spec 018)

## Menu (every signed-in page)

The places and the actions are separate lists:

```html
<ul class="nav-list nav-places"> My books · Catalog · Authors · Upcoming </ul>
<ul class="nav-list nav-actions" aria-label="Actions"> Add a book · Import · (Accounts) </ul>
```

The current place has `aria-current="page"`:
- **Authors** for `/authors` and `/authors/{id}`;
- **Catalog** for `/catalog`, `/catalog/series`, `/series/{id}` and `/books/{id}`.

## New and changed routes

| Method | Path | Result |
|---|---|---|
| GET | `/authors` | The Authors page. Query: `q`, `favorites=1`, `page` (bad values fall back to the defaults). HTMX requests get `partials/authors_list.html`. |
| GET | `/authors/favorites` | 302 to `/authors?favorites=1` |
| GET | `/catalog/series` | The Series view. Query: `q`, `page`. HTMX requests get `partials/series_list.html`. |
| GET | `/` with `upcoming=1` | 302 to `/upcoming` |
| GET | `/upcoming` | Gains a "Now out" section (`#now-out`) first, when there are any |
| POST | `/authors/{id}/favorite` | `back` may be `/authors`, with its query |

## Pages

- **Authors**, from top to bottom:
  - the heading;
  - the search box and the Favorites only checkbox;
  - the favorite notice;
  - the list, one row per author: name link, "pen name of …", "N books · M read", star;
  - Previous / Next;
  - "Authors with no books (n)".
- **Catalog**: a "Books | Series" switch under the heading, on both views.
- **Series view**: a search box, then one row per series (name link, "N books · M read"),
  then Previous / Next.
- **My books**:
  - no Upcoming checkbox;
  - no "My favorite authors" link;
  - no "Authors with no books" link;
  - when there are any, the line "<n> book(s) you want to read are now out" links to
    `/upcoming#now-out`.
- **Upcoming**: Now out, then On my list, then Also coming in the family catalog.
