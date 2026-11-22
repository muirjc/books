# UI contract: Stories in collections (spec 009)

This amends the `/catalog/books/{id}/edit`, `/entries/{id}`, `/series/{id}`,
`/catalog/authors/{id}/edit` and `/suggest/{kind}` rows of
[spec 001 ui-routes.md](../../001-family-reading-list/contracts/ui-routes.md), and adds the
routes below. Every POST needs the session CSRF token. Unknown ids, and a story that isn't
in the named book, return 404.

| Route | Behaviour |
|---|---|
| `GET /catalog/books/{id}/edit` | Adds `<h2>Stories in this book</h2>`. It is a list of "#n Series — Title" with an **Edit** link (`/catalog/stories/{sid}/edit`) and a **Remove** button (`POST …/stories/{sid}/remove`) per story, then an **Add a story** link (`/catalog/books/{id}/stories/add`). With none: "No stories recorded for this book." `?msg=story_added&story=<sid>` shows "Added the story “Title”." only when that story is in this book. `?msg=story_removed` / `story_deleted` show "Story removed from this book." / "Story deleted from the catalog." |
| `GET /catalog/books/{id}/stories/add` | `<h1>Add a story to “Book”</h1>` with fields title (combobox `kind=stories`, hidden `story_id`), authors (rows, filled with the book's authors), series (filled with the book's series) and number. Buttons: **Add story** and a **Cancel** link back to Edit book. |
| `POST /catalog/books/{id}/stories/add` | Checks in the order of research R5. Results: 303 back to Edit book with `msg=story_added&story=<sid>`; 422 for field errors; 409 for new-name prompts (spec 005); 409 when the number is taken, showing "#2.5 “Title” is already in the catalog, in Side Jobs." with an **Add that story to this book** button (`use_story=<sid>`) and the form kept, so the number can be changed. If the book already has the story: 303 back with `msg=story_already`, "That story is already in this book." |
| `GET /catalog/stories/{sid}/edit` | `<h1>Edit story “Title”</h1>` with the same fields, a **Save story** button, and "In: " links to each containing book's Edit book page. `?msg=saved` shows "Saved." |
| `POST /catalog/stories/{sid}/edit` | 303 to itself with `msg=saved`; 422; 409 for new-name prompts; 409 when the number is held by another story: "#n “Title” already has this number in the series." |
| `POST /catalog/books/{id}/stories/{sid}/remove` without `confirm=yes` | Confirm page. In other books too: "Remove “Title” from “Book”? It stays in: …". Only in this book: "Remove “Title” from “Book”? It isn't in any other book, so it will be deleted from the family catalog." Buttons: **Remove** (`confirm=yes`), plus a **Cancel** link. |
| `POST …/remove` with `confirm=yes` | 303 to Edit book with `msg=story_removed` or `msg=story_deleted`. |
| `GET /entries/{id}` | When the book has stories: "Stories in this book" lists "#n Series — Title", each series linking to `/series/{series_id}`, then a link "Edit the stories" to Edit book. |
| `GET /series/{id}` | Story rows (research R4) carry the class `series-story`: a badge "#n", the label "Story" (visually and for screen readers), the title, "In " plus the containing book links (to the member's entry, or `/books/add?book=<bid>&from_series=<series>`), then the status. Not on my list: one **Add “Book” to my list** link per containing book. Book rows with stories in this series add "Contains #1.5, #2.5". Progress reads "You've finished N of M books and K of L stories in this series." when L > 0. |
| `GET /catalog/authors/{id}/edit` | Adds a "Stories" list (title links to Edit story) after Books. Delete is offered only with no books and no stories, otherwise "This author can't be deleted while books or stories list them." |
| `GET /suggest/stories` | Story suggestions, `data-id` = story id, detail "#n Series · in Book". |
| `GET /suggest/books` | A book matched by a story title gets the detail "contains “Story title”". |
