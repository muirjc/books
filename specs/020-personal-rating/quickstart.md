# Quickstart: Personal Rating (spec 020)

Run the app as in [spec 001's quickstart](../001-family-reading-list/quickstart.md), with
migration `0008_personal_rating` applied (`alembic upgrade head`).

1. **Rate**: open an entry, choose "4 – Really liked it", save. The Rating field shows it
   selected, and the My books row shows "Rated 4 out of 5"; the book page shows it after your status.
2. **Clear**: choose "No rating" and save; the text is gone everywhere.
3. **Add a book** with "5 – Loved it": the new entry shows "Rated 5 out of 5".
4. **Sort and filter**: on My books, sort "Highest rated" (5s first, unrated last); filter
   "4 and up", then "Not rated". Repeat with JavaScript off.
5. **Privacy**: sign in as another member and open the same book's page: no rating shows.
6. **API**: `PATCH /api/v1/me/readings/{id}` with `{"rating": 6}` → 422; `{"rating": null}`
   clears it; `GET /api/v1/me/readings?sort=-rating&min_rating=4` lists the 4s and 5s.

Automated checks: `uv run pytest -k "020 or rating"`, `uv run pytest -m a11y`,
`uv run pytest -m perf`.
