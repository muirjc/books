# Research: Flow Fixes (spec 014)

Every change is a template change or a small route change. Nothing is stored, and no
dependency is added.

## R1 – Where Add a story returns to

**Decision**:
- Add story takes an optional `from=entry:<entry id>`, sent as a query value on GET and a
  hidden field on POST.
- The route parses it and checks the entry is the member's own and for this book. Only
  then does a save, add-another or cancel return to `/entries/<id>`. Otherwise it returns
  to `/catalog/books/<id>/edit#stories`, as today.
- Only ids are taken from the value, never a path, so it can't be an open redirect.
- Edit story takes `from=book:<book id>`: from Edit book's list, or from an entry page's
  list via that entry's book. The back link uses it if the story is in that book.
  Otherwise it uses the first book.

**Alternatives**: the `Referer` header is unreliable and not testable without JavaScript.
A free-text `next=` path would need open-redirect guarding.

## R2 – Add and add another for stories

**Decision**:
- A second submit button, `then=another`. On success it redirects to
  `/catalog/books/<id>/stories/add?added=<story id>` (plus `from=…`).
- The page shows "Added “#2.5 Publicity and Advertising”." for a story that is in this
  book, and nothing for any other id.
- The title field gets `autofocus` when the page opens after an add.
- Without the button, the redirects stay as today (`story_added` message on Edit book), or
  go to the entry page with `msg=story_added`.

## R3 – Back links (AC-06 to AC-09)

**Decision**: a new service read, `readings.entry_for_book(db, user_id, book_id) ->
ReadingEntry | None`. It goes through `ReadingEntryRepository(db, user_id).get_by_book`
(Principle I). Edit book and Summary use it. The links sit in a `<p class="back-link">` at
the top of `main`, before the `h1`.

## R4 – Navigation highlights (AC-10)

**Decision**: each route passes `active`:

| `active` | Pages |
|---|---|
| `list` | the entry page and My favorite authors |
| `catalog` | Catalog, every edit page, Summary, Add story, Edit story, series pages, author pages and Authors with no books |
| `import` | the import pages |

Rename the nav label to **Import**. A test walks the pages and checks `aria-current` on the
right tab.

## R5 – Add #next (AC-12)

**Decision**: add `SeriesView.next_number: int | None`. It is
`floor(max(book and story numbers)) + 1` when that is ≤ 999, else None. It is also None
when nothing is numbered. The template adds a row in the gap-row style after the last numbered row (before books
with no number), linking to
`/books/add?series=…&number=<next>&from_series=…`.

## R6 – Add a book prefills (AC-13, AC-14)

**Decision**: `GET /books/add` reads two more values:
- `anthology=yes` ticks the box (the spec 013 form flag). It works with `series=` and
  `from_series=`.
- `author=<id>` chooses an existing author, as row 0 with its id; an unknown or malformed
  id is ignored.

`series_start_form` and the new `author_start_form` build the form, as spec 006 R3 does.

## R7 – Admin confirmations (AC-16, AC-17)

**Decision**:
- `POST /admin/users/{id}` with `action=deactivate|make_admin` and no `confirm=yes`
  renders `admin/confirm_action.html` (200). It names the member and the action, and has
  a form posting the same action with `confirm=yes` plus a Cancel link.
- `reset-password` validates the password first: an invalid one gets today's 422 on
  Accounts. A valid one without `confirm=yes` renders the confirmation, with the password
  in a hidden field and not shown. With `confirm=yes` it resets.
- `reactivate` and `make_member` stay one step.
- The JSON admin API is unchanged: an API client acts deliberately.

**Note**: the confirmation page is a 200 GET-free render of a POST, as
`confirm_remove.html` already does for removing an entry.

## R8 – Change password link (AC-15)

**Decision**: add `<a href="/account/password">Change password</a>` to `account-actions` in
`base.html`, with `button-link` styling so it lines up with the two buttons. On a phone the
account area already wraps (spec 003); checked by the layout tests.

## R9 – My books and jump links (AC-18, AC-19, AC-05)

**Decision**:
- Move the favorites link into `#filter-extra`, right after the Author field, so the
  phone fold shows it with the filters.
- Entry page and Edit book get a `nav.jump-links` with `aria-label="On this page"`.
