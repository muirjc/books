# Contract: Summary draft pages (spec 012)

These rows are added to `specs/001-family-reading-list/contracts/ui-routes.md`.

| Method | Path | Form / query | Result |
|---|---|---|---|
| GET | /catalog/books/{id}/summary | — | Summary page, as today, with **Draft with AI** |
| POST | /catalog/books/{id}/summary/draft | `csrf_token`, `regenerate` (0/1), `text` (what was in the box) | 200: the Summary page with the draft (HTMX: the draft region partial), or with a failure alert and `text` kept. Status 200 for every outcome the member can act on; 404 for an unknown book; 403 for bad CSRF |
| POST | /catalog/books/{id}/summary | `csrf_token`, `text`, `draft_id` (optional) | As today: redirect with "Saved." The origin follows research R6 |
| GET | /catalog/books/{id}/summary/use-series | `name`, `number` | Confirmation page when a draft is unsaved (AC-21): **Save summary first** (form) or **Leave the draft** (link to Edit book) |
| GET | /catalog/books/{id}/edit | `suggest_series`, `suggest_number` (optional) | Edit book with the series fields pre-filled, unsaved, and the notice "Series and number suggested by the AI. Check them, then save." |
| POST | /entries/{id}/summary-draft | `csrf_token` | Starts a draft for the entry's book, then shows the Summary page with it (AC-22). 404 for another member's entry |
| POST | /books/add | the existing fields plus `action=draft_summary` | The form re-rendered with all fields, the summary filled in and a hidden `summary_draft_id`, or with a failure alert (AC-23). The book is not saved |

## Draft region (summary page)

- `<div id="summary-draft" role="region" aria-labelledby="draft-heading">` holds:
  - the notice (`role="status"`);
  - the textarea;
  - **Based on** (a list of links with `rel="noopener noreferrer"` and
    `target="_blank"`, with the visible text "(opens in a new tab)");
  - "Written by <model>";
  - the series hint;
  - the actions;
  - "N AI drafts left today."
- Failure messages use `role="alert"` and are tied to the textarea with
  `aria-describedby`.
- The HTMX request has an indicator with `role="status"`: "Drafting… this can take up to
  30 seconds". Buttons are disabled while it runs (`hx-disabled-elt`).
