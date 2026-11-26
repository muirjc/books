# UI contract: Stories without a series (spec 019)

## Display (AC-08)

| Place | With a series (as today) | Without a series |
|---|---|---|
| Book page, entry page, Edit book (`partials/book_stories.html`) | `#2.5 <a>Dresden Files</a> — Title` | `Title by Author, Author` (and "Also in …" on the book page) |
| Author page, Stories list | `#2.5 Dresden Files — Title · in …` | `Title · in …` (the page is already that author's) |
| Edit story | "All of <series>" link | no series link |
| Edit author | title only | title only |
| Series pages, progress, Add #next | listed | never listed |

Order in a book (AC-09): with a series, by series name then number; then without a series,
in the order added.

## Forms

**Add a book, story rows** (hint: "Leave the number and series blank for a story that isn't
part of a series. Leave the author blank to use all the book's authors."):

| Number | Series | Book has a series | Result |
|---|---|---|---|
| blank | blank | either | story without a series |
| given | blank | yes | the book's series |
| given | blank | no | "Story N: Choose a series for this story, or clear the number for a story that isn't part of a series" |
| blank | given | either | "Story N: Enter a number, or clear the series for a story that isn't part of a series" |
| given | given | either | as today |

**Add a story** (series starts with the book's) and **Edit story**: series and number both
or neither. Messages beside the field:
- series without number: "Enter a number, or clear the series for a story that isn't part of
  a series";
- number without series: "Choose a series, or clear the number for a story that isn't part
  of a series".

Everything typed is kept on a refusal; all forms work without JavaScript.
