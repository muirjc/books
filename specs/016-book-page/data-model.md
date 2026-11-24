# Data Model: Read-only Book Page (spec 016)

No schema change and no new entities. The page reads:

| Data | Source | Notes |
|---|---|---|
| Book (title, authors, series and number, release date, current summary) | `catalog.get_book` | Catalog; shared |
| Stories in the book, each with its series, number and containing books | `catalog.book_stories` → `Story.books` | Catalog; "Also in" = `Story.books` minus this book |
| Import source reference | `imports.source_ref` | Catalog |
| My entry (status, finished date) | `readings.entry_for_book(session user)` | Personal; owner only (Principle I) |

The only write reachable from the page is the existing spec 015 quick add, which creates
one reading entry (status Want to read) for the session user.
