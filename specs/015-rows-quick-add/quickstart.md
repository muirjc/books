# Quickstart: Consistent rows and quick Want to read (spec 015)

```bash
uv run pytest tests/integration/test_quick_add.py tests/integration/test_book_rows.py -q
uv run pytest -m a11y tests/a11y/test_rows_a11y.py
```

By hand:
1. On the Catalog, filter by an author and go to page 2.
2. Choose **Want to read** on a book: you're back on the same page at that row, with the
   notice, and the row shows a **Want to read** badge.
3. Repeat on an author page, on Upcoming, and on a series page (book and story rows).
