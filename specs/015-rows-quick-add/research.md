# Research: Consistent Book Rows and Quick Want to read (spec 015)

## R1 – The quick add route

**Decision**: `POST /books/{book_id}/want-to-read`, a form post with `csrf_token` and
`back`. It:

1. calls `services.readings.add_entry(book_id=…, status=want_to_read)`;
2. on `already_on_list`, changes nothing;
3. redirects (303) to `back` plus `wanted=<book id>` (or `already=<book id>`) and
   `#book-<id>`.

An unknown book is Not Found.

**Rationale**: it reuses the add path, with its Principle I repository and duplicate
check. A plain post works without JavaScript.

## R2 – The return address

**Decision**: `back` must fully match an allow-list:
- `/catalog`, `/upcoming`, `/authors/<uuid>` or `/series/<uuid>`;
- optionally `?` plus a query of URL-safe characters, with no `#`, backslash, control
  characters, or `//` anywhere.

Earlier `wanted` and `already` values are dropped from the query before adding the new
one. Anything else becomes `/catalog`.

**Rationale**: only internal paths from a fixed set are allowed, so it can't be an open
redirect.

## R3 – The notice

**Decision**: the four routes read `wanted` / `already` (a UUID). They look up my entry
for that book through `readings.entry_for_book` (spec 014) and pass it as
`quick_added` / `quick_already`. The partial `partials/quick_notice.html` shows the AC-02 /
AC-03 text. Nothing is shown for an id that isn't on my list.

## R4 – One row macro

**Decision**: `macros.html` gets `book_row(book, entry, back, with_series=true)`:

```
<li class="catalog-row" id="book-<id>">
  <a class="book-title" href="(my entry | Edit book)">title</a>
  <span class="catalog-detail"><span class="book-meta">authors · Series #n</span> · release</span>
  <span class="row-status">(status badge link | "Not on my list")</span>
  <span class="row-actions">(Want to read form + Add with details… link)</span>
</li>
```

- Catalog, author pages and Upcoming ("others") use it.
- Upcoming "mine" rows use it with `entry`, because their status was a plain badge.
- The existing class names (`catalog-row`, `book-title`, `book-meta`, `series-action`) are
  kept where tests and CSS use them. `catalog-mine` (the "On my list" link) becomes the
  status badge link, `a.badge.status-link`.

## R5 – Series rows

**Decision**: series rows keep their structure.
- `series-status` text becomes `<a class="badge status-link">` (with the finished date
  after it) when the book is on my list.
- The "Add to my list" link becomes the two actions.
- A story row's per-book adds become a Want to read form for each containing book.

## R6 – Upcoming target sizes

**Decision**: the button and link get the same 44 px minimum as `series-action`. They sit
in a wrapping flex container (`.row-actions`) so phones don't scroll sideways.
