# UI contract: Series viewer (spec 006)

Amends the `GET /series/{id}` and `GET, POST /books/add` rows of
[spec 001 ui-routes.md](../../001-family-reading-list/contracts/ui-routes.md).

## `GET /series/{series_id}`

| Case | Response |
|---|---|
| Series exists | `200`: progress line, then rows ([data-model.md](../data-model.md)) |
| Series exists, no catalog books | `200`: "The family catalog has no books in this series yet." + "Add a book to this series" |
| Unknown or malformed id | `404` (unchanged) |
| `?added=<entry_id>`, the viewer's own entry for a book in this series | as above, plus a status message "Added “Title” to your list." |
| `?added=` another member's, in another series, removed or malformed | as above, with no message |

Links in rows:

- Book on my list: the title links to `/entries/<entry_id>`.
- Not on my list: **Add to my list** → `/books/add?book=<book_id>&from_series=<series_id>`.
- Gap: **Add #n** → `/books/add?series=<series_id>&number=<n>&from_series=<series_id>`.

## `GET /books/add` (new optional parameters)

| Parameter | Valid | Invalid or unknown |
|---|---|---|
| `book` | form starts from that catalog book, shown as details (title · authors · series #n) with "Add a different book", not as editable fields; status Want to read | ignored |
| `series` + `number` | series and number filled in, status Want to read | ignored; an invalid `number` alone leaves the number blank |
| `from_series` | hidden `from_series` in the form | ignored |
| `after` (spec 004) | unchanged; takes precedence over `book` and `series` | unchanged |

## `POST /books/add`

New form field `from_series` (a UUID; invalid = absent). All checks and status codes are
unchanged.

| `then` | `from_series` names an existing series | Successful save |
|---|---|---|
| `list` | yes | `303 /series/<from_series>?added=<entry_id>` |
| `list` | no / absent | `303 /?msg=added` (unchanged) |
| `another` | any | `303 /books/add?after=<entry_id>` (spec 004, unchanged) |

Error, conflict and new-name pages keep `from_series` as a hidden field, as does the
ISBN-conflict "Add “…” to my list instead" form.
