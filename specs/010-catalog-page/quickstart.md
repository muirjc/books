# Quickstart: Catalog page (spec 010)

## Automated

```bash
uv run pytest tests/integration/test_catalog_page.py
timeout 900 uv run pytest -m a11y tests/a11y/test_catalog_a11y.py tests/a11y/test_layout_003.py
uv run pytest -m perf
```

## By hand

| Step | Expect |
|---|---|
| Sign in, choose **Catalog** in the navigation | "N books in the family catalog", by title, 50 a page |
| Search "butcher" | Only Jim Butcher's books; "N books match" |
| Search "Restoration" | *Side Jobs* (it contains the story) |
| Paste a book's ISBN-13 with hyphens | That book first |
| Sort by Series | Series books by series and number, books with no series last |
| Tick **Not on my list**, Apply | Your own books disappear; the count drops |
| Choose **Add to my list** on a book | Add a book, started from that book (spec 006) |
| Sign in as another member | Your books show **Add to my list** for them; nothing shows your status |
| Turn JavaScript off and repeat a search | The full page reloads with the results |
| Narrow the window to phone width | Rows wrap; **Sort and filter** folds the controls |
