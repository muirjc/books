# Quickstart: Delete an author with no books (spec 008)

## Automated

```bash
uv run pytest tests/integration/test_delete_author.py tests/contract/test_delete_author_contract.py
timeout 900 uv run pytest -m a11y tests/a11y/test_delete_author_a11y.py
uv run pytest -m perf
```

## By hand

| Step | Expect |
|---|---|
| Add an author through Add a book and then abandon the book, or use the API | My books shows "Authors with no books (1)" |
| Follow it and open the author | Edit author says no book lists it and offers Delete author |
| Delete author, then Delete | Back on the list with "Deleted “Name”."; the link on My books is gone |
| Open an author with books | Its books are listed; no Delete button |
