# Quickstart: AI Summary Drafts (spec 012)

## Automated checks (no network, no key)

```bash
uv sync
uv run pytest tests/unit/test_draft_rules.py tests/unit/test_claude_generator.py \
  tests/external/test_open_library_describe.py tests/integration/test_summary_drafts.py \
  tests/integration/test_draft_failures.py tests/integration/test_draft_cache.py \
  tests/integration/test_series_suggestion.py tests/integration/test_draft_entry_points.py \
  tests/contract/test_summary_drafts_contract.py -q
uv run pytest -m a11y tests/a11y/test_summary_drafts_a11y.py
```

All of them use `FakeSummaryGenerator` and recorded Open Library fixtures.

## Manual check against the real AI (costs a few cents)

1. Set a key in the environment where the app runs. Never put it in a file in the repo:
   `BOOK_TRACKER_ANTHROPIC_API_KEY=...`.
   Optional settings: `BOOK_TRACKER_AI_MODEL` (default `claude-opus-5-5`) and
   `BOOK_TRACKER_AI_DAILY_DRAFT_LIMIT` (default 10).
2. Start the app (see specs/001-family-reading-list/quickstart.md) and sign in.
3. Open a well-known book's Summary page and select **Draft with AI**. Expect within 30 s:
   - a 100–200 word draft;
   - sources (no Amazon or Goodreads);
   - "9 AI drafts left today".
4. Select **Draft with AI** again: the same draft, marked as drafted earlier, still 9
   left.
5. **Regenerate**: a new draft, 8 left.
6. Edit one word and save. The history shows "(AI draft, edited)" with its sources.
7. Unset the key and restart. **Draft with AI** says "AI drafts aren't set up", and saving
   by hand still works.

## On the Pi

Add `BOOK_TRACKER_ANTHROPIC_API_KEY` to the app's environment file on the Pi (the
maintainer does this; the key is never sent in chat or committed). Then run
`docker compose up -d app`. Without it, the feature reports "not set up" and the rest of
the app is unaffected.
