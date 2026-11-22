# Quickstart: Stories in collections (spec 009)

## Automated

```bash
uv run pytest tests/integration/test_stories.py tests/integration/test_series_stories.py \
  tests/unit/test_series_rows_stories.py tests/contract/test_stories_contract.py
timeout 900 uv run pytest -m a11y tests/a11y/test_stories_a11y.py
uv run pytest -m perf
```

## By hand

| Step | Expect |
|---|---|
| Add *Side Jobs* (Jim Butcher, no series) to your list as Finished | On your list |
| Edit book → Add a story: "Restoration of Faith", series The Dresden Files, number 1.5 | Back on Edit book with "Added the story “Restoration of Faith”." |
| Add #2.5 and #6.5 the same way | Three stories listed by number |
| Open another book → Add a story at The Dresden Files #2.5 | "#2.5 “…” is already in the catalog, in Side Jobs." and **Add that story to this book** |
| Open The Dresden Files series page | #1.5, #2.5, #6.5 story rows in order, "In Side Jobs · Finished"; progress mentions stories |
| Sign in as another member, open the series | Story rows say Not on my list, with Add “Side Jobs” to my list |
| Remove a story from its only book | Confirmation says it will be deleted; then "Story deleted from the catalog." |
| Type "Restoration" on Add a book | *Side Jobs* suggested, "contains “Restoration of Faith”" |
