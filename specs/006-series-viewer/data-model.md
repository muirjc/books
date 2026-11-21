# Data Model: Series Viewer (spec 006)

No schema change and nothing new is stored.

## SeriesView (computed, per request)

| Field | Meaning |
|---|---|
| `rows` | `SeriesRow` list in display order |
| `finished` | the viewer's Finished entries among the listed books |
| `total` | the number of book rows (gaps aren't counted) |

## SeriesRow

| `kind` | Fields | Shown as |
|---|---|---|
| `book` | `book`, `entry` (the viewer's own, or none) | number, title, authors, my status or **Not on my list** + **Add to my list** |
| `gap` | `first`, `last` (whole numbers) | "#first" or "#first–#last" · Not in the family catalog yet · **Add #first** |

## Start forms for Add a book (read only)

| Start | Fills | Status |
|---|---|---|
| `book=<id>` | `book_id`, title, authors (names + ids), series (name + id), number | Want to read |
| `series=<id>&number=<n>` | series (name + id), number | Want to read |
| `from_series=<id>` | hidden `from_series` (return page) | (unchanged) |
