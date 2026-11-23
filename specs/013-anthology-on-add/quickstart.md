# Quickstart: Anthology Stories on Add a Book (spec 013)

## Automated checks

```bash
uv sync
uv run pytest tests/unit/test_story_rows.py tests/integration/test_anthology_add.py \
  tests/integration/test_anthology_names.py tests/contract/test_anthology_contract.py -q
uv run pytest -m a11y tests/a11y/test_anthology_a11y.py
uv run pytest -m perf tests/perf -k anthology
```

## By hand (the app running as in specs/001-family-reading-list/quickstart.md)

1. Sign in and open **Add a book**. Enter *Side Jobs*, author Jim Butcher, series The
   Dresden Files, with no number.
2. Tick **This book is an anthology or collection**. Fill in row 1: *Restoration of Faith*,
   number 1.5.
3. Choose **Add another story** twice and fill in *Publicity and Advertising* (2.5) and
   *Something Borrowed* (6.5). Leave series and author blank.
4. Choose **Add to my list**. The notice reads "Added to your list, with 3 stories."
5. Open the Dresden Files series page. #1.5, #2.5 and #6.5 show as stories "In *Side
   Jobs*".
6. Repeat with JavaScript off. The story section is always visible and the buttons redraw
   the page.
7. Add another book with a row at Dresden #2.5. The row offers **Use that story**, and
   nothing is saved until it's answered.
