# Research: Read-only Book Page (spec 016)

## R1 – Where the page lives and what it loads

- **Decision**: `GET /books/{book_id}` in `web/routes/readings.py`, declared after
  `/books/add`. It loads:
  - `catalog.get_book` (404 when missing; the book carries its authors, series and current
    summary);
  - `catalog.book_stories`;
  - `imports.source_ref`;
  - `readings.entry_for_book(db, session user, book)`;
  - the spec 015 `quick.notice` for the `wanted` / `already` notice.
- **Rationale**: these services already exist, and the entry page and Edit book use the
  same ones, so the page shows the same things in the same way.
- **Alternatives considered**:
  - Making Edit book read-only for some members: rejected. Every member may edit the
    catalog, and the problem is landing on a form.
  - `/catalog/books/{id}`: rejected. `/catalog/...` holds the edit routes. `/books/...`
    already holds Add a book and the quick add, which are member actions on books.

## R2 – Title links

- **Decision**: book titles on these pages link to `/books/<id>`, whether or not the book
  is on my list:
  - `book_row` in `macros.html` (Catalog, author pages, Upcoming);
  - `series.html`: book rows, and each containing book on a story row (today a link to my
    entry when held, else plain text);
  - the book lists in `edit_author.html` and `edit_series.html`.

  The status badge keeps linking to my entry. `reading_list.html` and the Now out list in
  `list.html` (My books) are unchanged.
- **Rationale**: this is the decision made with the user on 2026-11-23. The badge is the
  way into my entry everywhere else.
- **Story titles** on Edit author stay links to the story edit page: that list is part of
  an editing page, and a page per story is out of scope.

## R3 – Return addresses

- **Quick add**: `_BACK` in `web/quick.py` gains `books/<uuid>`. On the book page the
  anchor is the page itself: the heading has `id="book-<id>"`, so the existing
  `#book-<id>` lands on it. `DROPPED_KEYS` still strips one-time notice keys. Any other
  path still returns to `/catalog`.
- **Add a story** (AC-12): the book page links to
  `/catalog/books/<id>/stories/add?from=page`. `_origin` in `routes/stories.py` learns the
  literal `page`. With it:
  - the form's back link goes to the book page;
  - after saving, it redirects to `/books/<id>?msg=story_added#stories-heading` (or
    `story_already`);
  - **Add another** keeps `from=page`.

  `page` carries no id, so it can only ever return to the book being edited. No new
  redirect target can be injected.
- **Add with details…**: it opens `/books/add?book=<id>` as on every row, and after saving
  goes where Add a book always goes (My books, with the added notice). Unchanged.

## R4 – "Also in" for stories

- **Decision**: `partials/book_stories.html` gains an optional `also_in` flag. When it's
  set (only on the book page), each story's line ends with "Also in “<title>”" for every
  entry in `story.books` other than this book, each linking to `/books/<id>`.
- **Rationale**: `Story.books` is already loaded by `book_stories` (mapper `BookRef`), so
  there's no extra query. The entry page and Edit book keep today's output (flag off).

## R5 – Notices on the book page

- **Decision**: the page shows the spec 015 `partials/quick_notice.html` for `wanted` /
  `already`, and a status notice for `msg=story_added` / `story_already`, reusing the entry
  page's wording.

## R6 – Performance

- **Decision**: there are four reads: the book with its relations, the stories with their
  books, the source reference, and my entry. The notice may add one more. A perf test
  times the page for a book with 50 stories in the 5,000-book catalog, and re-runs the
  Catalog, author and series budgets.
