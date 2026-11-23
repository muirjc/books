# Research: Author Page and Favorite Authors (spec 011)

## R1 – A user-bound favorites repository

**Decision**: `persistence/favorites.py` has `FavoriteAuthorRepository(db, user_id)`, built
like `ReadingEntryRepository`. Every statement filters on the bound user, and no method
takes a user id. Its methods are:

- `list()`: my favorite authors, by sort name;
- `has(author_id)`;
- `add(author_id)`: `INSERT … ON CONFLICT DO NOTHING`. A foreign-key violation (the author
  was deleted) becomes not found;
- `remove(author_id)`;
- `condition()`: an EXISTS on `Book`, true when one of the book's authors is a favorite of
  the bound user. This is the My books filter.

**Rationale**: Principle I puts the user filter in the data-access layer. A separate module
keeps the readings repository focused, and lets the coverage gate name the new module.

## R2 – The Author page view

`services/authors.author_view(db, user_id, author_id)` returns:

- the author;
- `groups`: a tuple of (series or none, rows). Each row is (book, my entry or none). Groups
  are ordered by series name, with the no-series group last. Rows are ordered by number
  (nulls last), then title;
- `stories`, from the existing `author_stories`;
- `favorite`: whether the viewer favorites the author;
- `delete_block`: `None`, `"mine"` or `"other"` (research R4). The page itself doesn't
  show it; Edit author does.

The books come from the existing `catalog.author_books` (by title), and are grouped and
sorted in Python. My entries come from `ReadingEntryRepository.list_books`.

## R3 – The My books filter value

The Author select gains `<option value="favorites">My favorite authors</option>`, after
**Any author**.

- The route reads `author_id=favorites` as the favorites filter. Any other value must parse
  as a UUID, as today.
- `ReadingEntryRepository.list` gains `extra: ColumnElement[bool] | None`, filled from the
  favorites repository's `condition()`. The condition is built with the same session user,
  so the filter stays inside user-bound code.
- The API takes `favorite_authors: bool`.

## R4 – The delete rule (constitution 2.0.0)

- **Unused**: `catalog._has_no_books()` stays "no book and no story". A new
  `_deletable()` adds "no favorite_author row", and is used by `delete_unused_author`,
  `unused_authors` and `unused_author_count`.
- **Conflicts**: `delete_author` raises `ConflictError("author_is_favorite")` when the
  author has no works but is favorited. It still raises `author_has_books` when works list
  the author. The RESTRICT foreign key `favorite_author_author_id_fkey` backstops a race:
  its IntegrityError is treated as "not deleted", then classified.
- **Edit author**: it asks the favorites repository (user-bound) whether *I* favorite the
  author, and the catalog whether *any* favorite exists (`catalog.author_favorited`, which
  is a count-free EXISTS). It shows the "mine" message if I do, otherwise the "other"
  message. Neither names a member or gives a count.

## R5 – The favorite button

- **Form**: `POST /authors/{id}/favorite` with `csrf_token` and `favorite=yes|no`, then 303
  to `/authors/{id}?msg=favorited|unfavorited`.
- **Status**: the "★ One of your favorite authors" line is static text. The star is
  `aria-hidden`.
- **Button**: it is a plain submit button whose name says what it does. `aria-pressed` was
  rejected: the button changes the page and the text already names the action.

## R6 – Author links in book rows

A macro `author_links(book)` renders each author as `<a href="/authors/{id}">name</a>`,
joined by ", ". It replaces `authors_line` in:
- My books rows;
- the Catalog;
- Upcoming;
- the series page.

The chosen-book line on Add a book keeps plain text.

The entry page and Edit book list each author as "<name>" (a link to the page) and keep
"Edit author “<name>”" beside it.

Inline links in a line of text are exempt from the 44 px rule (WCAG 2.5.8 inline
exception), as the series links already are.
