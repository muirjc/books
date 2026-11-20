# Data Model: Responsive Layout (spec 003)

No entities, columns, constraints or migrations change.

My books already loads each entry's `finished_on` and `times_read` (spec 001 data model).
The laptop row shows them as separate cells; nothing new is queried or stored.

| Data | Owner | Change |
|---|---|---|
| Book, author, series (catalog) | Family | None |
| Reading entry: status, finished_on, times_read, notes (personal) | Member | None; finished_on and times_read are now visible in laptop list rows |
