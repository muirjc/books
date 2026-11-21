# Quickstart: checking the series viewer (spec 006)

## Automated

```bash
uv run pytest tests/unit/test_series_rows.py               # ordering, gaps, collapsing
uv run pytest tests/integration/test_series_viewer.py      # page, privacy, add + return
uv run pytest -m a11y tests/a11y/test_series_viewer_a11y.py
uv run pytest -m perf                                      # includes the series page budget
```

## By hand

Run the app as in [001 quickstart](../001-family-reading-list/quickstart.md).

| Step | Expect |
|---|---|
| Open a book in The Dresden Files, then "All of The Dresden Files" | Every catalog book in the series in order, with your status, "Not on my list" for the others, and gap rows for missing numbers |
| Read the top line | "You've finished N of M books in this series." |
| Sign in as another member who has read a book you haven't | Your page still says "Not on my list" for it |
| Choose **Add to my list** on a row | Add a book with that book chosen, status Want to read |
| Save | Back on the series page, "Added “…” to your list.", and the row shows Want to read |
| Choose **Add #7** on a gap row, type a title and author, save | Back on the series page, with #7 filled |
| Phone width (390 px) | No sideways scroll; the Add links are full-size targets |
