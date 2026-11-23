# Feature Specification: AI Summary Drafts

**Feature Branch**: `012-ai-summary-drafts`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "AI summary drafts with review" (bead books-6w6; product spec
FR-07, FR-08, FR-14 and section 4). A member asks the AI to draft a book's summary,
reviews it, and can edit, accept, regenerate or discard it. Nothing is saved without
acceptance. The draft may also suggest the book's series and number.

Decisions made with the user on 2026-11-23:
- **Model:** Claude Opus 5.5 by default. The model is a server setting.
- **Sources:** Open Library's description and details, plus the AI's web search, with
  Amazon and Goodreads blocked.
- **Daily limit:** 10 drafts per member per day.
- **Series suggestion (FR-14):** in scope.

## Overview

Today a book's summary is written by hand on its Summary page
(`/catalog/books/{id}/summary`). The product was planned with AI-drafted summaries from the
start (product spec section 4), but they were never built. This feature adds them.

On the Summary page a member selects **Draft with AI**. The app gathers what permitted
sources say about the book and asks the AI for an original, spoiler-free summary of 100–200
words. The draft appears in the summary box, clearly marked as an unsaved AI draft, with the
web pages it was based on. The member can:
- **accept** it as it is, or after editing it, with **Save summary**;
- **regenerate** it, for a fresh draft;
- **discard** it, and write their own or leave the summary as it was.

Nothing reaches the family catalog until the member saves (Principle III). A saved summary
records whether it came from the AI unchanged (`ai`) or edited (`ai_edited`), with the model
and the source URLs.

When the AI finds a series and number for the book, the draft also offers it, for example
"Looks like The Dresden Files #3". The member can apply it through Edit book, where the
usual checks run.

### Example

Alice opens the Summary page of *Fool Moon*, which has no summary yet, and selects **Draft
with AI**:

| Part of the page | Shows |
|---|---|
| Notice | "AI draft, not saved yet. Check it, edit it if you like, then save it, or discard it." |
| Summary box | 160 words about Harry Dresden and a string of werewolf killings in Chicago |
| Based on | openlibrary.org/works/OL…, en.wikipedia.org/wiki/Fool_Moon |
| Series hint | "Looks like The Dresden Files #2" · **Use this series** |
| Actions | **Save summary** · **Regenerate** · **Discard draft** |
| Allowance | "9 AI drafts left today." |

She changes one sentence and saves. The family now sees her summary as the current one. The
history says "Written by Alice on 23 Nov 2026 (AI draft, edited)".

## Clarifications

### Session 2026-11-23

- **Q: Which model?** → Claude Opus 5.5 (`claude-opus-5-5`), set as a server setting so it
  can change without code changes.
- **Q: Where does the AI get its information?** → Open Library's description and details,
  plus the AI's own web search. Amazon and Goodreads are blocked, and every URL used is
  recorded.
- **Q: How many drafts per member per day?** → 10. The limit is a server setting.
- **Q: Is the series suggestion (FR-14) in scope?** → Yes. The member applies it through
  Edit book; nothing changes without their action.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Draft, review and accept a summary (Priority: P1)

A member asks the AI for a draft of a book's summary, reads it with its sources, edits it if
they like, and saves it as the family's summary, or discards it.

**Why this priority**: this is the feature. Everything else supports it.

**Independent Test**: with a fake AI, open a book's Summary page, select **Draft with AI**,
check the draft and its sources appear unsaved, save it unchanged (origin `ai`), draft again,
edit and save (origin `ai_edited`), and discard a third draft (nothing stored).

**Acceptance Criteria**:

- **AC-01**: **Given** a book's Summary page, **Then** it offers **Draft with AI** next to
  the summary box, with a hint saying the AI writes a draft for the member to check and
  that nothing is saved until they save it.
- **AC-02**: **Given** the member selects **Draft with AI**, **When** the draft is ready,
  **Then** the page shows:
  - the draft in the summary box, so it can be edited;
  - a notice: "AI draft, not saved yet. Check it, edit it if you like, then save it, or
    discard it.";
  - **Based on**: the source pages, each as a link that opens off-site;
  - the model that wrote it;
  - **Save summary**, **Regenerate** and **Discard draft**;
  - how many drafts the member has left today.
- **AC-03**: **Given** a draft is shown, **When** nothing is saved, **Then** the book's
  current summary and its history are unchanged, for every member.
- **AC-04**: **Given** a draft, **When** the member saves it unchanged, **Then** it becomes
  the book's current summary with origin `ai`, the model, the source URLs, the member and
  the time. **When** they change the text before saving, **Then** the origin is
  `ai_edited`, with the same model and sources. Saving keeps the older summaries in the
  history, as today.
- **AC-05**: **Given** the summary history, **Then** each summary says how it was written:
  "Written by Alice on 23 Nov 2026" for a hand-written one, with "(AI draft)" or "(AI
  draft, edited)" added for the others. An AI summary also lists its sources.
- **AC-06**: **Given** a draft, **When** the member selects **Discard draft**, **Then** the
  page returns to the summary box as it was before drafting, and nothing is stored.
- **AC-07**: **Given** JavaScript is off, **Then** drafting, regenerating, discarding and
  saving all work as full page loads. With JavaScript on, the draft replaces the summary box
  in place, and a "Drafting… this can take up to 30 seconds" status is announced while it
  waits.
- **AC-08**: **Given** a member saves a form claiming to be from a draft that the app did
  not produce, or whose draft was for another book, **Then** the summary is saved as
  `manual`. A member can't make hand-written text look AI-written, or the reverse.

---

### User Story 2 - Failures and limits fall back to writing by hand (Priority: P1)

When drafting can't work, the member is told why in plain words and can still write the
summary themselves. Each member has a daily allowance of drafts.

**Why this priority**: Principle III requires that no core feature depend on the AI. A
draft that fails or a limit that's reached must never block the Summary page.

**Independent Test**: with the fake AI set to each failure, select **Draft with AI** and
check the message, that the summary box keeps what was typed, and that **Save summary**
still saves a hand-written summary.

**Acceptance Criteria**:

- **AC-09**: **Given** each failure below, **When** the member selects **Draft with AI**,
  **Then** the page shows the message, keeps any text already in the summary box, and still
  lets them save a summary by hand:

  | Failure | Message |
  |---|---|
  | The AI isn't set up on this server | "AI drafts aren't set up. You can write the summary yourself." |
  | No answer within 30 seconds, or the AI service fails | "The AI didn't answer in time. Try again, or write the summary yourself." |
  | The sources say too little about the book | "The AI couldn't find enough about this book to write a summary. You can write one yourself." |
  | The AI declines to write it | "The AI couldn't write a summary of this book. You can write one yourself." |
  | The draft fails a check (AC-11, AC-12, AC-13) | "The AI's draft didn't pass our checks. Try again, or write the summary yourself." |
  | The daily limit is reached | "You've used your 10 AI drafts for today. You can write the summary yourself, or draft again tomorrow." |

- **AC-10**: **Given** a member, **Then** each request that reaches the AI counts against
  their daily allowance, whether it succeeds or fails, because each one costs money. Showing
  a cached draft (AC-15), and failures before the AI is asked (not set up, limit reached),
  don't count. The allowance resets at midnight in the family's time zone. One member's use
  never affects another's.
- **AC-11**: **Given** a draft that cites, or is based on, a page from a blocked site
  (Amazon or Goodreads, including their subdomains), **Then** it is rejected before it is
  shown (Principle IV).
- **AC-12**: **Given** a draft shorter than 60 words or longer than 250 words, **Then** it
  is rejected. (The AI is asked for 100–200; the wider band allows for small misses.)
- **AC-13**: **Given** a draft that repeats 12 or more consecutive words from a source
  description given to it, **Then** it is rejected, so publisher blurbs aren't copied
  (Principle IV).
- **AC-14**: **Given** the AI service is slow or down, **Then** every other page works as
  before, and no page waits on the AI except the draft request itself.

---

### User Story 3 - Reuse drafts and regenerate (Priority: P2)

A draft is kept for a while, so opening it again costs nothing. **Regenerate** asks for a
fresh one.

**Why this priority**: keeps cost down (Principle III requires the cache) and lets the
member try again when a draft isn't good.

**Independent Test**: draft a book twice and check the second is the cached draft and the
allowance is unchanged; regenerate and check a new draft appears and the allowance drops;
as another member, draft the same book and get the cached draft.

**Acceptance Criteria**:

- **AC-15**: **Given** a draft was made for a book within the last 30 days, **When** any
  member selects **Draft with AI** for a book with the same ISBN, or the same title and
  authors, **Then** that draft is shown without asking the AI, and it doesn't count against
  their allowance. The page says it was drafted earlier, with the date.
- **AC-16**: **Given** a draft is shown, **When** the member selects **Regenerate**, **Then**
  the AI is asked again (the cache is bypassed), the request counts against their
  allowance, and the new draft replaces the cached one.
- **AC-17**: **Given** a book's title, authors or ISBN change, **Then** a draft for the old
  details is no longer offered for it.
- **AC-18**: **Given** a cached draft, **Then** it is never shown as the book's summary
  anywhere. It appears only after **Draft with AI**, as an unsaved draft.

---

### User Story 4 - Apply a series suggestion (Priority: P2)

When the AI finds the book's series and number, the draft offers it. The member can apply
it through Edit book, with the usual checks.

**Why this priority**: saves typing (FR-14, a Should), but the summary is useful without it.

**Independent Test**: with a fake draft suggesting "The Dresden Files #2" for a book with no
series, check the hint, follow **Use this series**, check Edit book shows the suggestion
filled in but unsaved, and save it through the usual checks.

**Acceptance Criteria**:

- **AC-19**: **Given** a draft that suggests a series name and number different from the
  book's own, **Then** the page shows "Looks like <series> #<number>" with **Use this
  series**. A suggestion with no number shows the series alone. A suggestion that matches
  the book's series and number shows nothing.
- **AC-20**: **Given** the member selects **Use this series**, **Then** Edit book opens with
  the suggested series and number filled in, not yet saved, and a notice that they came from
  the AI. Saving goes through the existing checks: confirming a new series name (spec 005),
  the number rules and the series-number conflict (spec 001). Nothing changes if they don't
  save.
- **AC-21**: **Given** an unsaved draft on the Summary page, **When** the member selects
  **Use this series**, **Then** they are told first that the draft isn't saved, with **Save
  summary first** offered. The draft stays cached (AC-15), so drafting again later doesn't
  cost an allowance.

---

### User Story 5 - Draft from the entry page and Add a book (Priority: P3)

A member can start a draft from their entry and while adding a book, not only from the
Summary page.

**Why this priority**: convenience; the Summary page already covers the need.

**Independent Test**: from an entry page with no summary, follow **Draft with AI** and land
on the Summary page with a draft; on Add a book, fill in a title and author, select **Draft
summary with AI**, and check the summary field is filled with an unsaved draft; save the
book and check the summary's origin.

**Acceptance Criteria**:

- **AC-22**: **Given** an entry page, **Then** its Summary section offers **Draft with AI**
  next to **Write a summary**, which opens the book's Summary page and starts a draft.
- **AC-23**: **Given** Add a book with a title and at least one author filled in, **When**
  the member selects **Draft summary with AI**, **Then** the form comes back with
  everything they typed, and the Summary field holds an unsaved AI draft with its sources
  and notice (AC-02). Saving the book saves the summary with origin `ai` or `ai_edited`
  (AC-04). The same failure messages and allowance apply (AC-09, AC-10). Without a title or
  an author, the button explains what's needed first.

---

### User Story 6 - Drafts in the JSON API (Priority: P3)

API clients can request a draft and save it with its provenance.

**Why this priority**: the API mirrors the pages (Principle VII), but no client needs it yet.

**Independent Test**: request a draft for a book, check the response and that nothing is
stored, then save it through the summaries endpoint with the draft's id and check the origin.

**Acceptance Criteria**:

- **AC-24**: **Given** a signed-in client, **When** it requests a draft for a book, **Then**
  it gets the draft's id, text, source URLs, model, series suggestion (if any), whether it
  came from the cache, and the drafts left today. Nothing is stored in the catalog. The
  request may ask to regenerate. Failures return a clear error for each case in AC-09, and an
  unknown book returns 404.
- **AC-25**: **Given** a draft id, **When** a client saves a summary with it, **Then** the
  origin is `ai` or `ai_edited` as in AC-04. A missing or unknown draft id saves it as
  `manual` (AC-08).
- **AC-26**: **Given** the drafts endpoint and the changed save endpoint, **Then** the
  responses match the published contract, and no existing client breaks.

---

### Edge Cases

- **Two members draft the same book at once:** both may reach the AI and both count; the
  later draft replaces the earlier in the cache. Each member sees and saves their own draft.
- **The book's current summary changes while a member reviews a draft:** saving adds the new
  summary as current, as with hand-written summaries today; the history keeps the other.
- **A draft for a book deleted meanwhile:** saving gives Not Found, as today.
- **A source URL with tracking parameters:** stored as returned, at most 20 URLs, each up to
  2,000 characters.
- **The member edits a draft to empty:** the usual "Write a summary of 1 to 5,000
  characters" error.
- **Upcoming books (spec 007):** drafting works the same; sources may say little, which
  gives the "couldn't find enough" message.
- **Stories (spec 009):** only the book is summarized; stories have no summaries.
- **Another member's records:** drafts are catalog data and don't involve reading entries.
  The allowance count is per member and never shown to others.
- **Phone width:** the draft notice, sources and actions stack in the spec 003 layout.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Members MUST be able to request an AI draft of a book's summary from the
  Summary page, the entry page and Add a book (AC-01, AC-22, AC-23).
- **FR-002**: The draft MUST be shown for review with its sources, model and actions, and
  MUST NOT be stored in the catalog until the member saves it (AC-02, AC-03, AC-06, AC-18).
- **FR-003**: A saved draft MUST record origin `ai` or `ai_edited`, the model, the source
  URLs, the member and the time; only the app's own drafts can produce those origins (AC-04,
  AC-05, AC-08, AC-25).
- **FR-004**: The AI MUST be asked for an original, spoiler-free summary of 100–200 words,
  and drafts MUST be rejected when they cite a blocked site, fall outside 60–250 words, or
  copy 12 or more consecutive words from a source description (AC-11 – AC-13).
- **FR-005**: Every failure MUST leave the member able to write the summary by hand, with a
  plain message saying what happened (AC-09, AC-14).
- **FR-006**: Each member MUST have a daily allowance of AI requests, 10 by default (AC-10).
- **FR-007**: Drafts MUST be cached for 30 days outside the catalog, keyed by ISBN or by
  normalized title and authors; **Regenerate** MUST bypass the cache (AC-15 – AC-17).
- **FR-008**: The draft MUST offer a series suggestion when one is found, applied only
  through Edit book and its existing checks (AC-19 – AC-21).
- **FR-009**: Only book metadata and source text MUST be sent to external services (see
  Personal Data & Privacy).
- **FR-010**: AI requests MUST time out after 30 seconds.
- **FR-011**: The JSON API MUST offer drafts and accept the draft id when saving (AC-24 –
  AC-26).
- **FR-012**: The feature MUST work without JavaScript, meet WCAG 2.2 AA, and follow the
  spec 003 layouts (AC-07).

### Key Entities

- **Summary draft** (cache, not catalog): the draft text, its source URLs, the model, any
  series suggestion, the book details it was made from (the cache key), and when it was made.
  Kept 30 days. Never shown as a summary.
- **Draft allowance** (per member): how many AI requests the member has made on a given day.
- **Book summary** (existing catalog entity): gains nothing new; its existing origin, model
  and source URL fields are now filled for AI summaries.

## Data Ownership *(mandatory)*

| Data | Catalog or Personal | Read by | Written by |
|---|---|---|---|
| Book title, authors, series, ISBN, release date | Catalog | All members | Not written here (series only via Edit book, AC-20) |
| Summary draft and its sources (cache) | Catalog cache | Any member, as an unsaved draft | The app, when a member asks |
| Saved summary with origin, model, sources | Catalog | All members | Any member, by saving |
| Draft allowance count | Personal | Owner only (their own count) | The app |

- **Duplication check**: drafts are cached outside the catalog tables; nothing is copied
  into personal records.
- **Cross-user access**: the allowance is read and written only for the session's member.
  A cached draft is catalog data, shared by design, like the summary it may become.

## AI Involvement *(mandatory)*

- **Generated content**: a draft summary of 100–200 words, and a series name and number
  when found.
- **Approval step**: the draft is shown in an editable box marked as unsaved; only **Save
  summary** (or saving the book on Add a book) stores it. The series suggestion is applied
  only by saving Edit book.
- **Provenance stored**: origin (`ai` or `ai_edited`), model, source URLs, the member and
  the time, on the saved summary.
- **Fallback on failure**: the member writes the summary by hand; every failure says so
  (AC-09).

## External Sources *(mandatory for this feature)*

| Source | Access method | Terms of use permit this use? | Data sent |
|---|---|---|---|
| Open Library | Official API, already used by spec 002 | Yes: its API and data are openly licensed for this use | Title, author names, ISBN |
| Anthropic Claude API, with its web search | Official API, with a server-side key | Yes: Anthropic's commercial terms; web search is a built-in, permitted tool. Amazon and Goodreads are blocked in the search settings, and drafts citing them are rejected (AC-11) | Title, author names, series, number, ISBN, release year, and Open Library's description |

## Personal Data & Privacy *(mandatory)*

- **New personal data stored**: a per-member count of AI requests per day, the minimum
  needed to enforce the allowance. Old counts are deleted after 30 days.
- **Sent to external services**: book metadata and Open Library's description only. Never
  member names, notes, ratings, statuses, dates or any reading entry data (Principle IX).

## API Changes

- **New endpoints**: `POST /api/v1/books/{id}/summary-drafts` (request a draft; optionally
  regenerate).
- **Changed endpoints**: `POST /api/v1/books/{id}/summaries` accepts an optional draft id.
- **Breaking changes**: none; the new field is optional.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A member can go from an empty summary to a saved, reviewed AI summary in under
  one minute, excluding the AI's own time.
- **SC-002**: A draft appears, or a failure message replaces it, within 30 seconds of the
  request.
- **SC-003**: No summary is ever stored with origin `ai` or `ai_edited` except by a member
  saving a draft the app produced (checked by tests on every save path).
- **SC-004**: With the AI service unavailable, every page and every hand-written summary
  works exactly as before.
- **SC-005**: Automated checks report no WCAG 2.2 AA violations on the Summary page with a
  draft, a failure message and a series hint, at phone, tablet and desktop widths, and the
  draft-review-save journey works by keyboard alone.
- **SC-006**: Repeating a draft for the same book within 30 days costs no AI request.

## Assumptions

- **The AI key is a deployment secret.** The maintainer sets it on the server; it is never
  shown in a page, sent to the browser or logged. Without it, drafting reports "not set up"
  (AC-09) and the rest of the app is unaffected.
- **The model and the daily limit are server settings**, not admin pages. A settings page
  can follow if needed.
- **Cost:** at the chosen model a draft costs very roughly 5–15 US cents, including web
  search. At 10 drafts per member per day the worst case for a family of five is about
  $5–7 a day; normal use is far lower. Cached drafts cost nothing.
- **One draft at a time per page.** There is no comparison of several drafts side by side.
- **Google Books stays out** (decision books-zl3); Open Library and the AI's web search are
  the sources.
- **Tests never call the AI or the web.** A deterministic fake stands in for the AI, and
  recorded fixtures for Open Library (Principle V).
- **Summaries of stories, and drafting in other languages,** are out of scope.
