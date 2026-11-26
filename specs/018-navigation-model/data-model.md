# Data Model: Consistent Navigation (spec 018)

No schema change is planned. An index on `book_author(author_id)` is added only if the
perf tests show it's missing (research R5).

## Records read

- **Author**: name, sort name, real name.
- **Series**: name.
- **Book author** and **book.series_id**: used for the counts.
- **My favorite authors** (spec 011, personal).
- **My reading entries** (personal): Finished counts, and Now out (spec 007).

## Derived values (not stored)

- **Author row**:
  - the author;
  - catalog book count;
  - my Finished count;
  - whether the author is my favorite.
- **Series row**:
  - the series;
  - catalog book count;
  - my Finished count.
- **Now out count**: how many of my Want to read books came out in the last 30 days.
