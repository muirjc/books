# Data Model: Favorite Author Shortcuts (spec 017)

No schema change, no migration.

## Existing records used

- **Favorite author** (spec 011, `favorite_author`): (user, author), unique. It's read
  for the stars and the offer, and written by the star and offer buttons through the
  existing add and remove.
- **Reading entry** (`reading_entry`): there's one per (user, book). It's read to count
  my finished books by an author (`status = 'finished'`).
- **Book author** (`book_author`): which authors a book lists. Story authors are not used.

## Derived values (not stored)

- **Favorite set for a page**: the subset of the page's authors that are my favorites
  (`FavoriteAuthorRepository.among`).
- **Finished count**: for each author, how many distinct books by them are Finished on my
  list (`ReadingEntryRepository.finished_counts`).
- **Finish offer**: for the book named by `finished=<book_id>` in the address, when my
  entry for it is Finished, each author of the book who:
  - is not my favorite;
  - has a finished count of 2 or more.

  It's worked out each time a page shows it, and never stored.
