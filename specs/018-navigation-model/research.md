# Research: Consistent Navigation (spec 018)

## R1 – The menu

- **Decision**: `base.html` gets two lists in the `<nav>`:
  - **places**: `nav-list nav-places`, holding My books, Catalog, Authors and Upcoming;
  - **actions**: `nav-list nav-actions` with `aria-label="Actions"`, holding Add a book,
    Import, and Accounts for Admins.

  Layout:
  - **From 40em**, the actions list is pushed right with `margin-left: auto` and a thin
    separator.
  - **Below 40em**, both lists wrap. The actions list starts its own row, so the menu is
    at most two rows at 360 px (AC-18).

  `ACTIVE_TABS` in `web/rendering.py`:
  - `pages/author.html` and the new `pages/authors.html` mark `authors`;
  - `pages/series.html`, `pages/book.html` and the new `pages/catalog_series.html` stay
    on, or join, `catalog`;
  - `pages/favorite_authors.html` is deleted.
- **Rationale**: two lists make "places" and "actions" a visible, testable difference,
  rather than only a CSS gap.
- **Alternatives considered**: one list with a CSS divider. It was rejected because
  screen readers would hear one list of six or seven items, with no grouping.

## R2 – The Authors page

- **Route**: `GET /authors` in `web/routes/authors.py`. The order of the routes is `""`,
  `/favorites`, then `/{author_id}`.
- **Query**: `AuthorsQuery` (Pydantic, in `schemas/catalog.py`) with these fields. Bad
  values fall back to the defaults, as `CatalogQuery` does.
  - `q`: search text, through `search_text`;
  - `favorites`: on only for `"1"`;
  - `page`: through `parse_page`.
- **Query plan**: three queries in all.
  - **One page of authors**: `persistence.catalog.browse_authors(db, q, page, page_size,
    favorite, only_favorites)`. `favorite` is a `ColumnElement[bool]` condition on
    `Author`, from the new `FavoriteAuthorRepository.author_condition()`, which is bound
    to the session user like `condition()`.
    - Order: `favorite DESC`, then `lower(sort_name)`, then `id`.
    - Search: `ILIKE` on name, sort name and real name, with `like_patterns`.
    - Each row carries its catalog book count, from a `count()` subquery over
      `book_author`.
  - **The favorite marks**: `FavoriteAuthorRepository.among(ids)` (spec 017).
  - **The read counts**: `ReadingEntryRepository.finished_counts(ids)` (spec 017), for
    the page's (at most 50) authors only.
- **HTMX**: as on the Catalog, the search field updates `#authors-list` as the user
  types, through the partial `partials/authors_list.html`. Without JavaScript the form
  submits.
- **Stars**: `star_button` with `back` set to `favorites.page_back(request)`. The
  `/authors` index (no id) joins `_BACK` in `web/favorites.py`. An author page still gets
  the spec 011 `?msg=` address. The page includes `partials/favorite_notice.html` under
  the filters.
- **Empty states**:
  - **Favorites only, with no favorites**: the spec 017 text (how to add a favorite, and
    **Browse the Catalog**), moved into `partials/no_favorites.html`.
  - **A search with no matches**: "No authors match “…”." with a **Clear search** link.
- **Unused authors**: the "Authors with no books (n)" link moves here from My books
  (`catalog_service.unused_author_count`).
- **The old address**: `GET /authors/favorites` redirects (302) to
  `/authors?favorites=1`. Template links to it change to the new address.
- **Alternatives considered**: a column of letters to jump by. It was rejected because
  search does the same job and works on a phone.

## R3 – Upcoming and Now out

- **My books** (`my_list`):
  - When `upcoming=1` is in the address, it redirects (302) to `/upcoming` (AC-10). The
    checkbox, its hint, `kept["upcoming"]` and the "My favorite authors" link go from
    `list.html`.
  - `list_entries` keeps its `upcoming_after` parameter, because the JSON API uses it
    (spec 007), but the page no longer passes it.
  - The Now out box becomes one line in `partials/now_out_pointer.html`:
    "<n> book(s) you want to read are now out", linking to `/upcoming#now-out`.
- **Upcoming** (`upcoming_page`): adds `service.now_out(...)` and shows the existing box
  as a section, `<section id="now-out">` with an `<h2>Now out</h2>`, before "On my list".
- **Rationale**: the data and its rules (spec 007 R6) don't change. Only where they show
  does.

## R4 – The Catalog's Series view

- **Route**: `GET /catalog/series`. It doesn't clash with `/catalog/series/{id}/edit`.
  Its query is `SeriesQuery` (`q`, `page`).
- **Query plan**: two queries.
  - **One page of series**: `persistence.catalog.browse_series(db, q, page, page_size)`,
    by `lower(name)`. Each row carries its catalog book count.
  - **The read counts**: the new `ReadingEntryRepository.finished_counts_by_series(ids)`,
    a count of my Finished entries for books in each series.
- **The switch**: `partials/catalog_switch.html`, a `<nav aria-label="Catalog view">`
  holding two links, Books (`/catalog`) and Series (`/catalog/series`), with
  `aria-current="page"` on the current one. It's included on both views.
- **HTMX**: as on the Authors page, through `partials/series_list.html`.

## R5 – Performance

- Each new page runs at most three queries over a page of 50.
- `book_author` already has an index whose first column is `author_id` (checked during
  implementation; if it's missing, a migration adds one). `book.series_id` is indexed.
- The perf suite gains:
  - the Authors page (first page, a search, Favorites only);
  - the Series view;
  - Upcoming with Now out.

  Each is measured at 5,000 books and 1,500 authors.

## R6 – Specs this amends

- **Spec 007**: the "Upcoming only" filter is removed, and Now out moves to Upcoming.
  This affects AC text in spec 007 and its tests.
- **Spec 010**: the Catalog gains the Books | Series switch.
- **Spec 011 and 017**: My favorite authors becomes the Authors page with Favorites only.

Each of those specs gets a dated note pointing here. Old tests of the removed behaviour
are changed to test the new behaviour, keeping their `ac` markers and adding the `018`
ones.
