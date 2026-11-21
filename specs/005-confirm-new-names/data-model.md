# Data Model: Confirm New Author and Series Names (spec 005)

No schema change. Authors and series are created exactly as today, only later (after
confirmation).

## Page form fields (Add a book, a book's page, Edit book)

| Field | Sent by | Meaning |
|---|---|---|
| `confirm_author_<i>` | "Add “X” as a new author" button; then a hidden field | the member confirmed creating author X for row i; counts only while it equals the typed name |
| `use_author_<i>` | "Use “Y”" button | use catalog author Y (an id) for row i, whatever was typed |
| `confirm_series` | "Add “X” as a new series" button; then a hidden field | confirmed creating series X |
| `use_series` | "Use “Y”" button | use catalog series Y (an id) |

## NewName prompt (in memory, per request)

| Attribute | Meaning |
|---|---|
| `kind` | `author` or `series` |
| `index` | author row (0…19); `None` for the series |
| `name` | the typed name, normalized |
| `similar` | up to 3 `(id, label)` catalog records, best first |

## Reads

- `author_names()`: `(id, name, real_name)` for every catalog author
- `series_names()`: `(id, name)` for every catalog series

Both are catalog (shared) data, which every member can already see.
