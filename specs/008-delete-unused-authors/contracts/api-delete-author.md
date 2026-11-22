# API contract change: Delete an author (spec 008)

This change is additive. It is applied to
[spec 001 openapi.yaml](../../001-family-reading-list/contracts/openapi.yaml) and the
generated baseline.

`DELETE /api/v1/authors/{author_id}`, any signed-in member:

| Case | Response |
|---|---|
| No book lists the author | `204`, no body |
| Unknown author | `404` problem |
| Books list the author | `409` problem (`code: author_has_books`, `title: "This author has books"`) |
| Not signed in / password change required / bad CSRF | `401` / `403` / `403`, as other writes |
