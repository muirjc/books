# Research: Catalog Page (spec 010)

## R1 – One query function for the page

**Decision**: add `persistence.catalog.browse_books(db, *, q, isbn_13, sort, page,
page_size, exclude=None)`, which returns `(books, total, page)`:

1. It counts the matching books first.
2. It clamps the page to the last page, so a page past the end shows the last page (AC-06).
3. It reads one page with `limit` and `offset`. Authors and series are loaded by the
   models' existing selectin relationships.

**Rationale**: the same count-then-page shape as `ReadingEntryRepository.list`. With 5,000
rows, `ILIKE '%…%'` over the joined columns is a sequential scan of a small table, which is
well inside the budget (the type-ahead already does this in under 300 ms).

**Alternatives**: keyset paging. It was rejected because numbered pages, "Page n of m" and
sorting on several keys match My books, and the catalog is small.

## R2 – Matching shared with the type-ahead

**Decision**: lift `search_books`' conditions into `_book_matches(q, *, series)`. It
matches the title, an author's name or real name, and a story title, plus the series name
when `series=True`.

- The Catalog page uses `series=True`.
- The type-ahead keeps `series=False`, so its results are unchanged (spec Assumptions).
- An ISBN-13 search adds `Book.isbn_13 == isbn` to the OR, and sorts it first (AC-12), as
  the type-ahead does.
- Series matching needs `Book.series_id` joined to `Series`. `browse_books` always
  outer-joins it, which the Series sort needs too.

## R3 – The Not on my list filter stays in the user-bound repository

**Decision**: `ReadingEntryRepository.not_on_list()` returns
`~exists().where(ReadingEntry.user_id == self._user_id, ReadingEntry.book_id == Book.id)`.
The service passes it to `browse_books(exclude=…)`.

**Rationale**: Principle I. The only code that builds a condition on `reading_entry` is the
repository bound to the session user, so the catalog persistence never takes a user id.

**Alternatives**:
- A `user_id` parameter on `browse_books`. It was rejected because it puts a personal
  filter outside the user-bound layer.
- Filtering in Python after paging. It was rejected because the pages would come out short
  and the count would be wrong.

## R4 – Sorts

| Value | Label | Order |
|---|---|---|
| `title` (default) | Title (A–Z) | `lower(title)`, then id |
| `-title` | Title (Z–A) | `lower(title)` descending, then id |
| `author` | Author | first author's `lower(sort_name)` (the subquery `_order` uses), then title, id |
| `series` | Series | `lower(series.name)` nulls last, `series_number` nulls last, then title, id |
| `-added` | Newest in the catalog | `created_at` descending, then title, id |

An exact ISBN match goes before all of these. Ties always end on `Book.id`, so pages are
stable.

## R5 – Page, list and navigation layout

- **Navigation**: add `<li><a href="/catalog">Catalog</a></li>` after **Add a book**, with
  `active == "catalog"`. The spec 003 checks (`test_header_rows`, the 200% zoom check) need
  the links on one line at 640, 768, 1024 and 1280 px, for an admin too.
  - **Risk**: the extra link may not fit at the 1024 px laptop minimum.
  - **Mitigation**: the tests run first; if one fails, tighten the nav gap at that width.
    Don't shorten other labels.
- **Form**: a search form like My books' (`role="search"`, the `q`, `sort` and `not_mine`
  checkbox, **Apply** and **Clear**).
  - HTMX: `hx-get="/catalog" hx-target="#catalog-list" hx-push-url="true"`, triggered the
    same way.
  - On a phone, the sort and filter fold behind the existing **Sort and filter** toggle
    (the `data-fold` pattern).
- **Rows**: `ul.book-list.catalog-list` (`role="list"`). Each `li` holds:
  - the title link (`.book-title`, to Edit book);
  - `.book-meta`, with the authors and the series link;
  - `.book-release`, when the book is coming;
  - the action, either **On my list** (`a.catalog-mine`, to `/entries/{id}`) or **Add to
    my list** (`a.series-action`, with a visually hidden title).

  The rows use the flex layout of `.upcoming-list`: wrapping on a phone, one line where it
  fits, with the action at the end. Every target is at least `--target` high.
- **Count**: `p#list-count` (`aria-describedby` on the list), inside the `aria-live`
  region. It reads "N books in the family catalog" unfiltered and "N books match" filtered,
  with "1 book" for one.

## R6 – No index needed

The title sort orders 5,000 rows by `lower(title)` and takes 50. The existing
`book_series_id_idx` and the series name unique index cover the join. The perf test
(SC-001) is the check. If a sort misses the budget, add an index then, in a reversible
migration. Don't add one up front.
