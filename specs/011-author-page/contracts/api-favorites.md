# API contract change: Favorite authors (spec 011)

This change is additive. It is applied to
[spec 001 openapi.yaml](../../001-family-reading-list/contracts/openapi.yaml) and the
generated baseline. Every endpoint needs a signed-in member. Writes need the CSRF header.
401 and 403 are returned as elsewhere.

| Method and path | Responses |
|---|---|
| `GET /api/v1/me/favorite-authors` | 200 `Author[]`: the caller's favorites, by sort name |
| `PUT /api/v1/me/favorite-authors/{author_id}` | 204 (added, or already a favorite); 404 unknown author |
| `DELETE /api/v1/me/favorite-authors/{author_id}` | 204 (removed, or wasn't a favorite); 404 unknown author |
| `GET /api/v1/me/readings?favorite_authors=true` | as before, only books with at least one of the caller's favorite authors |
| `DELETE /api/v1/authors/{author_id}` | adds 409 `Conflict` with code `author_is_favorite`, when no book lists the author but a member favorites them. It doesn't say who. |
