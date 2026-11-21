# UI contract: Add a book with "Add and add another" (spec 004)

Amends the `GET, POST /books/add` row of
[spec 001 ui-routes.md](../../001-family-reading-list/contracts/ui-routes.md).

## `POST /books/add`

New form field `then`, a closed choice. The last value wins: the hidden field comes first,
the clicked button later.

| `then` | Successful save | Error or conflict |
|---|---|---|
| `list`, missing or anything else | `303 /?msg=added` (unchanged) | same page and status as today (422 / 409); hidden `then=list` |
| `another` | `303 /books/add?after=<entry_id>` | same page and status as today; hidden `then=another` |

All other fields, checks, messages and status codes are unchanged.

## `GET /books/add?after=<entry_id>`

| `after` | Page |
|---|---|
| The signed-in member's own entry | `200`, carry-over form ([data-model.md](../data-model.md)) and confirmation |
| Another member's, removed or not a UUID | `200`, the plain empty form; nothing about the entry shown |
| Absent | `200`, the plain empty form (unchanged) |

## Markup

In the add-book `<form>`, in DOM order:

1. `<input type="hidden" name="csrf_token">`, then `<input type="hidden" name="then" value="list|another">`
2. book fields, summary, reading fields (unchanged)
3. `<div class="form-actions">` containing:
   - `<button type="submit" name="then" value="list" class="button-primary">Add to my list</button>`
   - `<button type="submit" name="then" value="another">Add and add another</button>`

The ISBN-conflict form ("Add “…” to my list instead") also carries the hidden `then`.
The "Already on your list" choices (Read again, Open it) are separate actions on the
existing entry, not saves from this form, so they go to that entry as today; the member
returns to Add a book to continue the run (AC-16).

On the carry-over page only:

- above the form: `<p class="notice" role="status" id="added-notice">Added “<a href="/entries/{id}">{title}</a>” to your list.</p>`;
- the Title input has `autofocus`, and its `aria-describedby` includes `added-notice`.

## Layout

`.form-actions` is a wrapping flex row with a 0.75rem gap. Buttons keep the 44 px minimum
target. There is no sideways scroll from 360 px up, and the spec 003 form-column rules are
unchanged.
