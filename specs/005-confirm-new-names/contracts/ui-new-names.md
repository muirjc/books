# UI contract: confirming new author and series names (spec 005)

Applies to `POST /books/add`, `POST /entries/{id}` (with book fields) and
`POST /catalog/books/{id}/edit`. It amends their rows in
[spec 001 ui-routes.md](../../001-family-reading-list/contracts/ui-routes.md).

## Outcomes of a save

| Situation | Status | Saved |
|---|---|---|
| Every author and series picked, carried over, the book's own, or confirmed | as today (303) | yes |
| An unpicked name exactly matches a catalog name | 409, "Already in the catalog" (unchanged) | nothing |
| An unpicked, unconfirmed name not in the catalog | 409, new-name prompt | nothing |
| Field errors (422) | 422, as today, with any new-name prompts shown too | nothing |

## Prompt markup (per new name, inside the same form)

Under the field (`author_name_<i>` or `series_name`):

```html
<p class="field-error" id="author_name_0-error">“J DM Robb” is not in the family catalog yet</p>
<div class="conflict" id="author_name_0-new">
  <p>Did you mean:</p>
  <button type="submit" name="use_author_0" value="<id>">Use “J.D. Robb”</button>   <!-- 0–3, best first -->
  <button type="submit" name="confirm_author_0" value="J DM Robb">Add “J DM Robb” as a new author</button>
</div>
```

- **Error summary:** the field error text is also listed in the page's error summary, with
  a link to the field.
- **No similar names:** "Did you mean:" and the "Use" buttons are left out.
- **Series:** the same markup with `series_name`, `use_series` and `confirm_series`, and the
  button text "Add “…” as a new series".
- **Confirmed names:** each one is rendered as `<input type="hidden" name="confirm_author_<i>"
  value="…">` near its field. That is before any button with the same name, so a clicked
  button's value wins.
- **Button choice:** the spec 004 hidden `then` is unchanged.

## Not changed

- the JSON API (`/api/v1/...`);
- Import from Open Library;
- type-ahead suggestions.
