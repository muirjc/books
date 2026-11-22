# Quickstart: Upcoming Books (spec 007)

Run the app as in [spec 001 quickstart](../001-family-reading-list/quickstart.md); the
migration `0003_upcoming_books` runs with `alembic upgrade head`.

## By hand

1. **Add a book:**
   - enter a release date a few months ahead, tick Pre-ordered and save;
   - My books shows "Coming <date> · Pre-ordered".
2. **Filter:** turn on **Upcoming only**. Only that book shows, and Clear turns the filter
   off.
3. **Upcoming page:**
   - open **Upcoming**; the book is under On my list;
   - as a second member, add another future-dated book;
   - back as the first member, it shows under Also coming, with Add to my list.
4. **Now out:**
   - edit the first book's release date to 5 days ago;
   - My books shows "Now out: <title> (pre-ordered)";
   - set it to 40 days ago, and the notice goes;
   - set it back to 5 days ago and mark the book Reading, and the notice goes.
5. **The entry page** shows "Released <date>" for a past date.
6. **Without JavaScript:** repeat steps 1–3.

## Tests

```bash
uv run pytest tests/unit/test_upcoming.py tests/integration/test_upcoming_books.py \
  tests/contract/test_upcoming_contract.py tests/migrations
timeout 900 uv run pytest -m a11y tests/a11y/test_upcoming_a11y.py
uv run pytest -m perf -k upcoming
```
