# Quickstart: Consistent navigation (spec 018)

```bash
uv run pytest tests/integration/test_navigation.py -q
uv run pytest -m a11y tests/a11y/test_navigation_a11y.py
uv run pytest -m perf tests/perf/test_navigation_perf.py
```

By hand (see the [UI contract](contracts/ui-navigation.md)):
1. Check the menu: My books · Catalog · Authors · Upcoming, then Add a book · Import. On
   a 360 px phone it takes at most two rows. At 1,024 px the account actions take a
   second row (spec 003 AC-08, amended).
2. Choose Authors and type "prat". Then turn on Favorites only. Star an author and see the
   notice.
3. Open `/authors/favorites`. It lands on Authors with Favorites only on.
4. On My books there's no Upcoming checkbox, and the Now out line links to Upcoming,
   where Now out comes first.
5. On the Catalog, choose Series, search, and open a series.
