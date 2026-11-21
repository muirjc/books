# Quickstart: checking the responsive layout (spec 003)

## Automated

```bash
uv run pytest tests/integration/test_layout_markup.py      # server HTML: row cells, fold state
uv run playwright install chromium                         # once
uv run pytest -m a11y tests/a11y/test_layout_003.py        # widths, rows, header, zoom, axe
uv run pytest -m a11y                                      # all a11y, incl. specs 001 and 002
uv run pytest -m perf                                      # SC-006: My books under 1 s at p95
```

## By hand

Run the app as in [001 quickstart](../001-family-reading-list/quickstart.md). Then, in a
desktop browser with responsive design mode, or on the real devices:

| Check | Width | Expect |
|---|---|---|
| My books | 1,440 | one row per book with date finished and times read; filters on one row; at least 12 books visible |
| My books | 820 (iPad) | one row per book: title, authors, status, finished |
| My books | 390 (iPhone) | two lines per book; "Sort and filter" button folds sort and filters; at least 6 books visible |
| My books with `?status=reading` | 390 | sort and filters shown open |
| A book's page | 1,440 | Book details beside My reading; Save below |
| A book's page | 820 | series + number on one row; status + date on one row |
| Header (admin) | 1,024 | one row; Accounts link included |
| Header | 768 | nav links on one row |
| Any page | 1,280 at 200% zoom | tablet layout; no sideways scroll |

On the Pi, after deploy, open https://books.local on the iPad (portrait and landscape)
and an iPhone.
