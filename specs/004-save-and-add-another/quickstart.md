# Quickstart: checking "Add and add another" (spec 004)

## Automated

```bash
uv run pytest tests/unit/test_add_another_forms.py        # next number, carry-over mapping
uv run pytest tests/integration/test_add_another.py       # flow, PRG, cross-user, conflicts
uv run pytest -m a11y tests/a11y/test_add_another_a11y.py # widths, focus, no-JS, axe
uv run pytest -m a11y                                     # all a11y, incl. specs 001-003
```

## By hand

Run the app as in [001 quickstart](../001-family-reading-list/quickstart.md).

| Step | Expect |
|---|---|
| Add a book: "Grave Peril", Jim Butcher, The Dresden Files #3, Finished; choose **Add and add another** | Still on Add a book; "Added “Grave Peril” to your list." with a link; cursor in Title |
| Look at the form | Jim Butcher, The Dresden Files, number 4, Finished; title, ISBN, date, summary, notes empty |
| Type "Summer Knight", choose **Add and add another** | Added; next form suggests number 5 |
| Reload the page | No new book; the same confirmation |
| Type "Death Masks", press Enter | Added; goes to My books, as today |
| With JavaScript off, repeat the first step | Same result |
| Phone width (390 px) | Both buttons visible, no sideways scroll |
