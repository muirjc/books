# Quickstart: Author page and favorite authors (spec 011)

## Automated

```bash
uv run pytest tests/integration/test_author_page.py tests/integration/test_favorite_authors.py \
  tests/contract/test_favorites_contract.py tests/integration/test_migrations.py
timeout 900 uv run pytest -m a11y tests/a11y/test_author_a11y.py
uv run pytest -m perf
```

## By hand

| Step | Expect |
|---|---|
| On My books, select an author's name in a row | The Author page: series groups, my statuses, Add to my list |
| Choose **Add to my favorite authors** | "Added to your favorite authors."; ★ line; Remove button |
| Open **My favorite authors** | The author listed |
| My books → Author: **My favorite authors** | Only books by favorite authors |
| Sign in as another member, open the same author | Not marked as a favorite |
| Create an author with no books; another member favorites them; open Edit author | "A family member has this author as a favorite, so they can't be deleted." No Delete |
