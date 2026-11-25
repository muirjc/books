# UI contract: Favorite author shortcuts (spec 017)

## Changed route

| Method | Path | Change |
|---|---|---|
| POST | `/authors/{author_id}/favorite` | New optional form field `back`. When it's an accepted page (research R2), the route redirects there (303). The page's one-time keys are dropped, and `favorited=<author_id>` or `unfavorited=<author_id>` is added, ending `#favorite-notice`. Without `back`, or when it's refused, it redirects to `/authors/<id>?msg=favorited\|unfavorited`, as today. `favorite` must be `yes` or `no` (422 otherwise). An unknown author returns 404. |

Accepted `back` paths are:
- `/books/<uuid>`;
- `/authors/<uuid>`;
- `/entries/<uuid>`, mine only;
- `/`;
- `/series/<uuid>`;
- `/books/add`.

Each may have a query string.

## Pages

| Page | Change |
|---|---|
| `/books/{id}` | Each byline author is followed by a star form (`back=/books/<id>`). Below the byline is the `#favorite-notice` notice when `favorited` / `unfavorited` names an author. |
| `/entries/{id}` | Each "All books by <author>" line in More has a star form (`back=/entries/<id>`). The `#favorite-notice` notice shows above that list. The offer (below) shows near the top. |
| `/`, `/series/{id}`, `/books/add?after=…`, `/entries/{id}` | Read `finished=<book_id>`. When my entry for that book is Finished, they show the offer: "You've finished <n> books by <author>." with **Add <author> to my favorite authors** (posts `favorite=yes` and `back` = this page). After it's accepted, the `#favorite-notice` notice shows in its place. |
| `/authors/favorites` | When empty, it shows the instructions and a **Browse the Catalog** link (`/catalog`). |

## Redirects that gain `finished=<book_id>`

- `POST /books/add` with status Finished, to any of its destinations.
- `POST /entries/{id}` when the status changes to Finished.

## The star button

- It's a `<button type="submit">` holding `<span aria-hidden="true">☆</span>` (or ★), plus
  visually hidden text "Add <author> to my favorite authors" or "Remove <author> from my
  favorite authors".
- It's at least 44 × 44 CSS px.
- It comes directly after the author's link in the reading order.

## Unchanged

- The author page's own button and its `msg=` notices (spec 011).
- The JSON API.
- List rows.
- The HTMX My books list partial.
