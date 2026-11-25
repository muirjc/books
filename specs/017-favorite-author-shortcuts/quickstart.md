# Quickstart: Favorite author shortcuts (spec 017)

```bash
uv run pytest tests/integration/test_favorite_shortcuts.py -q
uv run pytest -m a11y tests/a11y/test_favorite_shortcuts_a11y.py
uv run pytest -m perf -k "book_page or entry_page or finish"
```

By hand (see the [UI contract](contracts/ui-favorites.md)):
1. Open a book page. Tap the ☆ after an author's name. The page returns with "Added
   <author> to your favorite authors." and a ★. Tap it again to remove the favorite.
2. Open My entry for the same book. The star in More shows the same state.
3. With no favorites, open My favorite authors. Follow **Browse the Catalog**.
4. Finish one book by an author (not a favorite). There's no offer.
5. Finish a second book by them. The page you land on offers **Add <author> to my favorite
   authors**. Tap it, and the author is a favorite and the offer is gone.
6. As another member, check that none of the first member's favorites show as filled stars.
