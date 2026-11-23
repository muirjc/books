# Research: AI Summary Drafts (spec 012)

## R1 – Calling Claude: SDK, model, tools and output shape

**Decision**:
- Use the official `anthropic` Python SDK (2.x), `AsyncAnthropic`, with the key passed
  explicitly from settings (`BOOK_TRACKER_ANTHROPIC_API_KEY`), `timeout=30`,
  `max_retries=0`. The app never relies on ambient credentials.
- Model from settings, default `claude-opus-5-5`, `output_config={"effort": "medium"}`
  (the model's default, set explicitly). Thinking is left at its default (adaptive);
  Opus 5.5 rejects disabling it.
- Tools:
  - `web_search_20260209` named `web_search`, `max_uses: 3`, `blocked_domains` listing
    Amazon's main storefront domains and `goodreads.com` (R4).
  - A client tool `submit_summary_draft` with `strict: true` and
    `additionalProperties: false`, which the prompt tells the model to call exactly once:
    `{status: "ok" | "not_enough_information", summary: string, source_urls: [string],
    series_name: string | null, series_number: string | null}`.
  - `tool_choice` stays `auto`; Opus 5.5 rejects forced tool choice.
- The loop sends a `pause_turn` message back unchanged and stops at the first
  `submit_summary_draft` call; the tool is never answered, because its input is the result.
  If the turn ends without the call, the draft fails as `ai_declined`.
- `stop_reason == "refusal"` becomes `ai_declined`. Server-side refusal fallback is enabled
  (`betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`), and the model
  recorded is `response.model`, the model that actually answered.
- Each draft is one member request. An `asyncio.timeout(30)` around the whole loop enforces
  FR-010 even across `pause_turn` resumes.

**Rationale**:
- A strict client tool gives a validated, structured result without
  `output_config.format`. That format can't carry web-search citations, and the citations
  are needed to record sources.
- Web search runs on Anthropic's side, so no fetching code of ours touches third-party
  sites.

**Alternatives considered**:
- `output_config.format` JSON: risks conflicts with citations, and gives no `status`
  channel beyond free text.
- Raw `httpx`: the claude-api guidance requires the SDK when one exists.
- A cheaper model: the user chose Opus 5.5 (spec Clarifications); the model is a setting.

## R2 – The prompt

**Decision**: a fixed system prompt (cacheable; no dates or ids in it) that says:
- write an original, spoiler-free summary of 100–200 words, covering no more than the
  opening premise;
- use your own words, and never quote or closely paraphrase publisher blurbs or reviews;
- use the given Open Library description and up to three web searches;
- cite only pages you actually used;
- if the sources disagree about which book this is, or say too little, answer
  `not_enough_information` instead of guessing;
- give a series name and number only when a source states them.

The user message holds only book metadata (R7): title, authors, series and number,
ISBN-13, release year, and Open Library's description when found. Each field is labelled,
and the text is wrapped as data, not instructions.

**Rationale**: product spec section 4 guardrails, and constitution Principles III and IV.

## R3 – The Open Library description

**Decision**: add `describe_book(title, authors, isbn13)` to the Open Library adapter
(`sources/open_library.py`) and to the `BookSource` protocol. It returns
`BookDescription(work_url, description) | None`:
- with an ISBN: `/isbn/{isbn}.json`, then that edition's first work;
- otherwise: `/search.json?title=…&author=…&limit=1&fields=key`;
- then `/works/{key}.json` for `description`, which is a string or `{value: …}`.

It uses the existing client, user agent, rate limiter and 10 s timeout. Open Library being
down is not a failure: the draft goes on with web search only.

The answer is cached for 24 hours in the existing `source_lookup_cache`, as spec 002 does
(Principle III: source lookups MUST be cached):
- a new kind, `book_description`;
- the key is `sha256(draft_key)` in hex, because the column holds at most 300 characters;
- "nothing found" is cached too, as `{"found": false}`;
- Open Library being unreachable is not cached. A description of more than
4,000 characters is cut at a word boundary. Tests use recorded fixtures.

**Rationale**: Principle IV (adapters behind the protocol). Open Library is already the
permitted source.

## R4 – Blocked sites

**Decision**:
- `domain/drafts.py` has `BLOCKED_DOMAINS = ("amazon.com", "amazon.co.uk", "amazon.ca",
  "amazon.com.au", "amazon.de", "amazon.fr", "amazon.in", "amazon.co.jp",
  "goodreads.com")` for the search tool. The API matches subdomains.
- After the answer, `is_blocked(url)` rejects any source URL whose host is, or ends with,
  `.amazon.<anything>` or `.goodreads.com`, or is exactly `amazon.<anything>` or
  `goodreads.com`. It runs over both the draft's `source_urls` and every citation URL in
  the response. Any hit rejects the draft (AC-11).

**Rationale**: the tool filter keeps the pages out; the post-check is the constitution's
"rejected before it is shown", and it covers country storefronts missing from the list.

## R5 – Checks on the draft text

**Decision**, as pure functions in `domain/drafts.py`, each unit-tested:
- `word_count(text)` must be 60–250 (AC-12).
- `copies_source(text, description, run=12)`: lower-case, keep word characters, and look
  for any 12-word sequence shared with the Open Library description (AC-13). Web pages
  aren't available as text, so only the description is compared; the prompt covers the
  rest.
- Sources: keep the URLs the model lists that are among the search-result URLs, the cited
  URLs or the Open Library work URL. Drop others, keep at most 20, each up to 2,000
  characters, and de-duplicate. If a draft cites nothing and has no Open Library
  description, it fails as `not_enough_information`. A draft must be based on something.
- `series_number` is parsed with the existing `parse_series_number`; an unparseable one is
  dropped, but the series name is kept (AC-19).

## R6 – The cache and draft identity

**Decision**: a `summary_draft` table (data-model). Each produced draft is a row with its
own id, kept 30 days.
- **Key:** `draft_key(isbn13, title, authors)` is `ta:<normalize_title(title)>|<sorted
  normalized author names>`, prefixed by `isbn:<isbn13>|` when the book has an ISBN. The
  title and authors are part of an ISBN key too, so fixing a title never brings back a
  draft written for the old details (AC-17; PR #32 review).
- **Lookup:** the newest row for the key that is younger than 30 days.
- **Regenerate** inserts a new row. It doesn't delete the old one, so a member still
  reviewing an earlier draft can save it with its id.
- Rows older than 30 days are deleted when a draft is written.
- **Saving with a draft id** (AC-04, AC-08, AC-25):
  - Load the row, check its age (30 days) and that its key equals the book's current key.
  - Then compare normalized text (whitespace collapsed, stripped): equal means `ai`,
    different means `ai_edited`.
  - Otherwise, the summary is `manual`, and no model or sources are stored.
- The cache is never read by any summary display (AC-18).

**Rationale**: Principle III requires the cache, keyed this way and outside the catalog
tables. Keeping old rows makes draft ids stable under concurrent regenerates.

## R7 – What is sent, and secrets

**Decision**:
- The AI request is built only from a `BookFacts` value (title, authors, series, number,
  ISBN, release year) and the Open Library description. No user id, name or reading data
  is in scope where it is built; a unit test asserts the request has only those keys.
- The key is a `SecretStr` setting, never logged; request logging already excludes bodies.
- With no key, `UnconfiguredGenerator` raises `ai_not_configured` without any network call.

## R8 – The daily allowance

**Decision**: an `ai_draft_usage(user_id, day, count)` table, reached only through
`DraftUsageRepository(db, user_id)`, a bound user in the style of spec 011's favorites.
- **Before asking the AI**, `reserve(day, limit)` runs:
  `INSERT … VALUES (user, day, 1) ON CONFLICT (user_id, day) DO UPDATE SET count =
  ai_draft_usage.count + 1 WHERE ai_draft_usage.count < :limit RETURNING count`.
- **No row back** means the limit is reached (AC-10). The reservation is committed before
  the AI call, so a failure still counts; a cached draft never reserves.
- `left(day, limit)` reports the remainder.
- **Day** is `today(request)`, the server's time zone, as elsewhere in the app.
- Rows older than 30 days are deleted on reserve.
- The module goes on the coverage-critical list.

**Rationale**: Principle I (bound repository); atomic under concurrent requests.

## R9 – The generator interface and wiring

**Decision**:
- `sources/summary_generator.py` defines a `SummaryGenerator` protocol:
  `async def draft(self, facts: BookFacts, description: BookDescription | None) ->
  GeneratedDraft`.
- `GeneratedDraft(status, text, source_urls, cited_urls, series_name, series_number,
  model)`. It raises `AiUnavailable` (timeout, connection, 5xx, 429) or `AiDeclined`.
- Implementations:
  - `ClaudeSummaryGenerator` in `sources/claude.py`;
  - `UnconfiguredGenerator`;
  - tests use `FakeSummaryGenerator` (in `tests/fakes.py`), scripted per test.
- `create_app(..., summary_generator=None)` picks Claude when a key is set, and
  `UnconfiguredGenerator` otherwise. Tests always pass a fake. The generator is on
  `app.state.summary_generator`, exposed as a dependency like `book_source`.
- `services/drafts.py` holds the use case:
  1. cache lookup, unless regenerating;
  2. reserve an allowance;
  3. get the Open Library description;
  4. call the generator. One time limit (30 s) covers steps 3 and 4: the AI gets what the
     Open Library lookup left;
  5. run the checks (R4, R5);
  6. store the row;
  7. return a `DraftView`.

  Both the pages and the API call it.

## R10 – Pages and the no-JavaScript path

**Decision**:
- **Summary page:** a `POST /catalog/books/{id}/summary/draft` form (CSRF-protected),
  with `regenerate` as `0` or `1`.
  - Success re-renders the Summary page with the draft in the textarea, a hidden
    `draft_id`, the notice, sources, model and allowance (AC-02).
  - With HTMX, the form region is swapped, and an `hx-indicator` live status says
    "Drafting… this can take up to 30 seconds" (AC-07).
  - On failure, the page re-renders with the message in an alert, and the textarea keeps
    the posted `text`.
- **Discard draft:** a button posting to `POST /catalog/books/{id}/summary/discard` with
  `before_text`: the box's text from before the first draft, carried in a hidden field
  through every Regenerate. The page comes back with that text (AC-06).
- **A draft id is kept** (hidden `draft_id`) through a failed Regenerate and a rejected
  save, so AI text still in the box never saves as `manual` (PR #32 review).
- **Save summary:** posts `text` plus `draft_id` to the existing save route. The existing
  route gains the optional `draft_id`.
- **Entry page:** a small POST form, **Draft with AI**, to the same draft route, followed
  by the Summary page. It isn't a GET link, because drafting spends the allowance.
- **Add a book:** a second submit button, `name="action" value="draft_summary"`, in the
  same form. The add route then validates only that a title and an author are present,
  drafts from the typed details (no book id: the cache key is computed from the details),
  and re-renders the form with every field kept, the summary filled in and a hidden
  `summary_draft_id`. Saving the book passes that id to the summary save. The origin check
  uses the new book's key.
- **Use this series:** a submit button in the summary form, posting `text` and `draft_id`
  to `POST /catalog/books/{id}/summary/use-series`, so edits to the draft aren't lost.
  - That page (AC-21) offers **Save summary first** (posts the text, `draft_id` and
    `then=series` to the save route, which then redirects to Edit book) and **Leave the
    draft** (a link to Edit book).
  - The suggestion is read from the stored draft, never from the request.
  - Edit book (`?suggest_draft=<draft id>`) pre-fills its series fields from that stored
    draft, unsaved, with a notice. The draft must be this book's own and less than 30
    days old; otherwise there is no suggestion. A crafted link can't show an "AI
    suggested" notice. Saving runs the existing checks.

## R11 – The JSON API

**Decision**:
- `POST /api/v1/books/{id}/summary-drafts` with body `{regenerate: bool = false}` returns
  200 `SummaryDraft`. Errors use the existing problem format:

  | Status | `code` |
  |---|---|
  | 404 | unknown book |
  | 429 | `draft_limit_reached` |
  | 503 | `ai_not_configured` |
  | 503 | `ai_unavailable` |
  | 422 | `not_enough_information` |
  | 422 | `ai_declined` |
  | 422 | `draft_rejected` |

- `POST /api/v1/books/{id}/summaries` gains an optional `draft_id` (non-breaking).
- `Summary` responses already carry `origin`, `model` and `source_urls`; they are now
  filled for AI summaries.
