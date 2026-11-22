# Research: Stories in Collections

## R1 – Tables

**Decision**: three new catalog tables.

- `story`: title, series (NOT NULL), number (NOT NULL), audit columns.
- `story_author`: ordered authors, the same shape as `book_author`.
- `book_story`: (book_id, story_id) links, primary key on the pair.

There is a unique index on `story (series_id, series_number)`. The book table is unchanged.

**Rationale**: a story collected twice is one row with two links (FR-002, FR-003).
Uniqueness lives in its own table, so a story can share a number with a book (AC-06) while
two stories cannot.

**Alternatives**:
- Story rows per book (number on the link): rejected, because the same story would
  duplicate.
- Reuse `book` with a "kind" column: rejected, because every list, search and entry query
  would have to exclude stories.

## R2 – "A story is in at least one book"

**Decision**: enforced in the one write path that can break it. `remove_story` deletes the
link, then runs `DELETE FROM story WHERE id = :id AND NOT EXISTS (SELECT 1 FROM book_story
WHERE story_id = :id)` in the same transaction. Creating a story and linking it to its
first book happen in one savepoint. No book delete exists (spec 001), and
`book_story.book_id` is `ON DELETE CASCADE` only so tests can clean up.

**Rationale**: "at least one child row" isn't a declarative constraint in PostgreSQL. A
deferred constraint trigger would do it, but nothing else in the schema uses triggers
(Principle VIII). The conditional delete is atomic, like spec 008's.

**Race**: someone links the story to a book while another member removes its last link.
- If the link commits first, the conditional delete sees it and keeps the story.
- If the delete wins, the link insert fails on `book_story_story_id_fkey`. That is mapped to
  Not Found ("That story was just deleted").

## R3 – Story status on the series page

**Decision**: there is a new per-member repository method,
`ReadingEntryRepository.list_books(book_ids)`. The series page reads the viewer's entries
for the books in the series plus every book that contains one of the series' stories. A
story's status is the best of those entries: Finished, then Reading, then Want to read. The
date shown is the latest `finished_on` among the Finished ones.

**Rationale**:
- Nothing is stored (FR-009).
- The read goes through the user-bound repository (Principle I).
- The method sits in a coverage-critical module, so it gets the cross-user test there.

## R4 – Row order and gaps

**Decision**: `series_rows` merges books and stories into one ordered list.
- Numbered rows go by number; at the same number the book comes before the story (AC-10).
- Unnumbered books come last, by title.
- Gap working uses the numbers of both books and stories (AC-12).
- Progress counts books as today, plus `K of L` stories when L > 0.

## R5 – Add a story form

**Decision**: reuse `AddBookForm` / `parse_add_book`, plus a story-only check that requires
a series and a number. That brings in the new-name prompts, author rows, series combobox
and conflict handling unchanged (spec 005, FR-006). The story fields partial includes the
same combobox partials as `book_fields.html`. It has no ISBN, release date or entry fields.

**Order of checks on POST**:
1. `use_story` ("Add that story to this book") links that story.
2. A `story_id` from a title suggestion links that story, if its title still matches what
   was typed. Without JavaScript, editing the text doesn't clear the id, the same rule as
   `_chosen_author`.
3. Field errors return 422.
4. New-name prompts return 409.
5. With an existing chosen series, a story already at that series and number returns 409
   with the choice (AC-05). This runs before any author or series is created.
6. Resolve authors and series, then create and link the story in one savepoint. A race on
   the unique index gives the same 409 choice.

## R6 – Return and messages

- **Saving a story:** it returns to the book's Edit book page, with
  `?msg=story_added&story=<id>`. The page names the story only if that story is in this
  book. The id is looked up rather than echoing a name from the URL, so a crafted link
  can't show false text (the spec 008 lesson).
- **Edit story:** it returns to its own page with "Saved.". The page lists the containing
  books.
- **Remove:** it returns to the book with "Story removed from this book." or "Story deleted
  from the catalog.".

## R7 – Search by story title

**Decision**: `search_books` adds `EXISTS (book_story JOIN story WHERE story.title ILIKE
…)`. The Add a book suggestion route then asks `story_matches(book_ids, q)` for the first
matching story title per book, and shows it as the detail "contains “…”". The API search
response shape is unchanged.

## R8 – Authors with stories (spec 008)

**Decision**:
- `_has_no_books()` becomes "no `book_author` and no `story_author` row".
- `story_author_author_id_fkey ON DELETE RESTRICT` is the backstop; spec 008 already maps
  any `IntegrityError` to the conflict.
- Edit author lists the author's stories under the books, and offers Delete only when there
  are neither.
- The API's 409 keeps its code and title (`author_has_books`, "This author has books"), so
  spec 008's contract is unchanged. The UI text says "books or stories".

## R9 – API shape

**Decision**:
- `GET /books/{id}/stories`
- `POST /books/{id}/stories`, taking either `{story_id}` or `{title, author_ids, series_id,
  series_number}`. It returns 201 when linked and 200 when the book already had it.
- `DELETE /books/{id}/stories/{story_id}` returns 204.
- `GET /stories/{id}`
- `GET /stories?series_id=` lists by number.
- `PATCH /stories/{id}`

A conflict on the number returns 409 `Conflict` with code `story_number_taken`, plus
`existing_id` and `existing_label` ("#2.5 Publicity and Advertising").

**Rationale**: adding a `stories` field to `Book` would load stories for every book in
every list. A sub-resource keeps the existing endpoints unchanged and non-breaking.
