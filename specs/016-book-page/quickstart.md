# Quickstart: Read-only book page (spec 016)

```bash
uv run pytest tests/integration/test_book_page.py tests/integration/test_book_rows.py -q
uv run pytest -m a11y tests/a11y/test_book_page_a11y.py
uv run pytest -m perf -k book_page
```

By hand (see the [UI contract](contracts/ui-book-page.md)):
1. On the Catalog, tap a book that isn't on your list. The book page shows its details,
   summary and "Not on my list".
2. Tap **Want to read**. You're back on the book page with the notice, a **Want to read**
   badge and **Open my entry**.
3. Open a collection's page. Each story shows its series place, and a story also in another
   book shows "Also in “…”", linking to that book's page.
4. Use **Add a story** from the book page. After saving you're back on the book page.
5. On My books, a title still opens your entry.
