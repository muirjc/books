# Data Model: Author Page and Favorite Authors (spec 011)

## New table `favorite_author` (personal)

| Column | Type | Rule |
|---|---|---|
| `user_id` | uuid | NOT NULL, FK `app_user(id)` ON DELETE CASCADE |
| `author_id` | uuid | NOT NULL, FK `author(id)` ON DELETE RESTRICT (`favorite_author_author_id_fkey`) |
| `created_at` | timestamptz | NOT NULL, default now() |

- **Primary key** `(user_id, author_id)`: one favorite per member and author.
- **Index** `favorite_author_author_id_idx (author_id)`: the delete rule's EXISTS.

## Changed rule

An author is *deletable* (spec 008) when no book or story lists them **and** no
`favorite_author` row names them. Migration `0005_favorite_authors` is reversible: its
downgrade drops the table.
