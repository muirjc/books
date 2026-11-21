# Data Model: Save and Add Another (spec 004)

No schema change and nothing new is stored. The feature reads existing records to pre-fill
a form.

## Carry-over mapping (read only)

From the signed-in member's own **reading entry** (personal) and its **book** (catalog):

| Form field | Source | Rule |
|---|---|---|
| `author_name_i`, `author_id_i` | `book.authors[i]` | every author, stored order |
| `series_name`, `series_id` | `book.series` | when the book is in a series |
| `series_number` | `book.series_number` | `floor(n) + 1`; blank when none |
| `status` | `entry.status` | same status |
| title, `book_id`, `isbn_13`, `finished_on`, `summary`, `notes` | none | empty |

The entry is read with the existing owner-filtered `get_entry`; another member's entry is
`NotFoundError`, which gives the plain empty form.
