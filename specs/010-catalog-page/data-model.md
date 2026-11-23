# Data Model: Catalog Page (spec 010)

No schema change and no migration.

## Read models (in code only)

- **CatalogRow**: `book` (the domain Book: title, authors, series, number, release date) and
  `entry` (the viewer's own ReadingEntry for the book, or none).
- **CatalogPage**: `rows`, `page` (after clamping to the last page), `page_size` (50), and
  `total` (the matching books).

## Reads

| Read | From | Bound to |
|---|---|---|
| Matching catalog books, counted and one page | `book`, `book_author`, `author`, `series`, `book_story`, `story` | Catalog (all members) |
| Whether each listed book is on my list, and my entry | `reading_entry` | Session user (`ReadingEntryRepository.list_books`) |
| Not on my list filter | `reading_entry` | Session user (`ReadingEntryRepository.not_on_list`) |
