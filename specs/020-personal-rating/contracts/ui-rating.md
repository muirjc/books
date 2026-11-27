# UI contract: rating (spec 020)

## Rating field (entry page and Add a book)

```html
<div class="field">
  <label for="rating">Rating (optional)</label>
  <select id="rating" name="rating">
    <option value="">No rating</option>
    <option value="1">1 – Didn't like it</option>
    <option value="2">2 – It was OK</option>
    <option value="3">3 – Liked it</option>
    <option value="4">4 – Really liked it</option>
    <option value="5">5 – Loved it</option>
  </select>
</div>
```

- Placed after Times read / Date finished, before Pre-ordered, in `partials/entry_fields.html`.
- An invalid value: "Choose a rating from 1 to 5, or No rating" beside the field
  (`aria-describedby`), everything typed kept.

## Display

- My books row: `<div class="book-rating">Rated 4 out of 5</div>`, absent with no rating.
- Entry page: no extra line; the Rating field shows the saved rating.
- Book page (spec 016): the `row-status` line adds " · Rated 4 out of 5" for the viewer's own
  entry only.

## My books

- Sort select gains "Highest rated" (`sort=-rating`) and "Lowest rated" (`sort=rating`).
- A new filter select, label "Rating": Any rating (`""`), 5 (`rating=5`), 4 and up (`4`),
  3 and up (`3`), 2 and up (`2`), Rated (`rated`), Not rated (`unrated`).
- Kept in the address with the other filters; Clear removes it; works with JavaScript off.
