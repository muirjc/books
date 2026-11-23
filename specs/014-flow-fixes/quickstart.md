# Quickstart: Flow Fixes (spec 014)

```bash
uv run pytest tests/integration/test_flow_fixes.py tests/integration/test_flow_fixes_admin.py -q
uv run pytest -m a11y tests/a11y/test_flow_fixes_a11y.py
```

By hand (the app running as in specs/001-family-reading-list/quickstart.md):

1. Open a book on My books that has no stories. Under **Stories in this book**, choose
   **Add a story**, then **Add and add another**, twice. Choose **Add story**: you're back
   on the entry page, which lists the stories.
2. Open Edit book from the Catalog. It shows **Back to “…”** and **Jump to: Stories in
   this book**.
3. On a series page, check the **Add #next** row and **Add a collection with stories in
   this series**.
4. On an author page, choose **Add a book by this author**.
5. In the header, choose **Change password**.
6. As an admin on Accounts, choose **Deactivate** on a member: a confirmation shows.
   Cancel changes nothing.
