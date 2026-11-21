# Quickstart: checking new-name confirmation (spec 005)

## Automated

```bash
uv run pytest tests/unit/test_similar_names.py                 # matching, SC-002 typo table
uv run pytest tests/integration/test_confirm_new_names.py      # three pages, choices, rollback
uv run pytest -m a11y tests/a11y/test_confirm_new_names_a11y.py
uv run pytest -m a11y                                          # all a11y, incl. specs 001-004
```

## By hand

Run the app as in [001 quickstart](../001-family-reading-list/quickstart.md), with "J.D.
Robb" and the series "In Death" in the catalog.

| Step | Expect |
|---|---|
| Add a book "Naked in Death", type author "J DM Robb" (don't pick), Add to my list | Nothing saved; error summary "“J DM Robb” is not in the family catalog yet"; buttons "Use “J.D. Robb”" and "Add “J DM Robb” as a new author" |
| Choose "Use “J.D. Robb”" | Book added with J.D. Robb; no new author |
| Add another with a genuinely new author "Ann Leckie" | Prompt with only "Add “Ann Leckie” as a new author"; choose it → added |
| Type series "In Deth" | Prompt offers "Use “In Death”" |
| On a book's page, change the author to a typed new name and save | Prompt; book and reading unchanged until a choice |
| Pick an author from the suggestions | No prompt |
| JavaScript off | Same behaviour |
