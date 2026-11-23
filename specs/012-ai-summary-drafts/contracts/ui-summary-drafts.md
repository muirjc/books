# Contract: Summary draft pages (spec 012)

These rows are added to `specs/001-family-reading-list/contracts/ui-routes.md`.

| Method | Path | Form / query | Result |
|---|---|---|---|
| GET | /catalog/books/{id}/summary | — | Summary page, as today, with **Draft with AI** |
| POST | /catalog/books/{id}/summary/draft | `csrf_token`, `regenerate` (0/1), `text` (what was in the box) | 200: the Summary page with the draft (HTMX: the draft region partial), or with a failure alert and `text` kept. Status 200 for every outcome the member can act on; 404 for an unknown book; 403 for bad CSRF |
| POST | /catalog/books/{id}/summary | `csrf_token`, `text`, `draft_id` (optional), `then` (optional, `series`) | As today: redirect with "Saved." The origin follows research R6. With `then=series` and a draft that suggests a series, redirect to Edit book with the suggestion |
| POST | /catalog/books/{id}/summary/use-series | `csrf_token`, `text`, `draft_id` (the **Use this series** button submits the summary form here) | Confirmation page (AC-21): **Save summary first** (posts `text`, `draft_id` and `then=series` to the save route, which then redirects to Edit book with the suggestion) or **Leave the draft** (link to Edit book). The suggestion comes from the stored draft, not the request |
| GET | /catalog/books/{id}/edit | `suggest_series`, `suggest_number` (optional) | Edit book with the series fields pre-filled, unsaved, and the notice "Series and number suggested by the AI. Check them, then save." |
| (entry page) | — | — | The entry page's **Draft with AI** is a small form posting `csrf_token` to `/catalog/books/{book_id}/summary/draft`, so it needs no route of its own (AC-22) |
| POST | /books/add | the existing fields plus `action=draft_summary` | The form re-rendered with all fields, the summary filled in and a hidden `summary_draft_id`, or with a failure alert (AC-23). The book is not saved |

## Draft region (summary page)

- `<div id="summary-draft" role="region" aria-labelledby="draft-heading">` holds:
  - the notice (`role="status"`);
  - the textarea;
  - **Based on** (a list of links with `rel="noopener noreferrer"` and
    `target="_blank"`, each followed by the visible text "(opens in a new tab)"; long URLs
    wrap at phone width);
  - "Drafted by <model>";
  - the series hint;
  - the actions;
  - "N AI drafts left today."
- Failure messages use `role="alert"` and are tied to the textarea with
  `aria-describedby`.
- The HTMX request has an indicator with `role="status"`: "Drafting… this can take up to
  30 seconds". Buttons are disabled while it runs (`hx-disabled-elt`).
