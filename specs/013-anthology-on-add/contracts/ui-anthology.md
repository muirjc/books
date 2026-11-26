# UI contract: Add a book with stories (spec 013)

All changes are on `GET/POST /books/add`. No new routes.

## Form additions (shown only when no catalog book is chosen)

```text
[ ] This book is an anthology or collection             (name=anthology value=yes)

Stories in this book                                    (h2, id=stories-heading)
  Hint: Leave Series blank to use the book's series, and Author blank to use all
  the book's authors.
  ┌ fieldset "Story 1" ───────────────────────────────────────────┐
  │ Title*        [story_title_0           ]                      │
  │ Number*       [story_number_0]                                │
  │ Series        [story_series_name_0  ▾ ] (combobox, id hidden) │
  │ Author        [story_author_name_0  ▾ ] (combobox, id hidden) │
  │ [Remove story 1]       (action=remove_story:0; only if 2+ rows)│
  └───────────────────────────────────────────────────────────────┘
  [Add another story]            (action=add_story; absent at 50 rows,
                                  replaced by "50 stories is the most for one save.")
```

- **Existing story chosen** (`story_id_{i}`): the row shows "#2.5 Publicity and
  Advertising (The Dresden Files), already in the catalog", plus **Remove story N**.
- **Taken number** (AC-13): beside the row, "#2.5 *Publicity and Advertising* is already in
  the catalog, in *Side Jobs*." Then the button **Use that story**
  (`name=use_story_{i} value=<id>`) and "or change the number".
- **New-name prompts** (spec 005) appear beside the first field with each new name.

## Actions on POST /books/add

| `action` | Result | Status | Writes |
|---|---|---|---|
| `add_story` | redraw + 1 empty row, focus on its title | 200 | none |
| `remove_story:{i}` | redraw without row i, focus on heading | 200 | none |
| `use_story_{i}` button | row i becomes that existing story; redraw | 200 | none |
| (save buttons) | as today, plus stories | 303 / 409 / 422 | all or nothing |

## Redirects after a save

- `/?msg=added&stories=N`
- `/books/add?after=<entry>&stories=N`
- `/series/{id}?added=<entry>&stories=N`
- `/entries/{id}?msg=stories_not_added` (AC-20)

Each notice adds "with N stories" (N ≥ 1).

## JavaScript (progressive)

`app.js`: `[data-anthology-toggle]` hides `#stories` when it is unticked on load, and
toggles it on change. Nothing else depends on JavaScript.

*Amended 2026-11-26 by [spec 019](../../019-optional-story-series/contracts/ui-stories.md): a row with no number and no series is a story without a series; a series with no number is refused.*
