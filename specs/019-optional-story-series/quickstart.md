# Quickstart: Stories without a series (spec 019)

```bash
uv run alembic upgrade head          # 0007_optional_story_series
uv run pytest tests/integration/test_story_series_optional.py tests/integration/test_migrations.py -q
uv run pytest -m a11y tests/a11y/test_story_series_optional_a11y.py
uv run pytest -m perf tests/perf/test_story_series_optional_perf.py
```

By hand (see the [UI contract](contracts/ui-stories.md)):
1. Add a book, tick the anthology box, and add three stories with titles and authors only.
   The book page lists them in that order, with no numbers or series.
2. On a collection with a series, add a numbered story with a blank series: it takes the
   book's series. Type a series with no number: it's refused on that row.
3. Edit a story without a series and give it a series and number: it appears on that
   series page. Clear them again: it leaves the series page.
4. `uv run alembic downgrade -1` is refused while a story has no series.
