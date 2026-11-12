# Database Conventions

PostgreSQL with pgvector is the local default. Docker Compose currently runs
only the database. See the [local development guide](../../guides/local-development.md)
for commands and port configuration.

## Schema and Transactions

- Define business schemas only from concrete requirements. Do not invent models,
  fields, relations, or sample data to populate the scaffold.
- Migration `0001` enables the `vector` extension and creates no business tables.
- Follow [backend conventions](backend.md) for sessions, transactions, and startup.
- Select the embedding model, dimensions, distance metric, access filters, and
  indexing requirements before defining vector storage. Existing Protocols do not
  establish those choices.

## Migration Safety

1. Identify the exact target database and inspect migration history before changes.
2. Determine whether a migration has already been applied or shared. Do not rewrite
   shared migration history; add a new migration for deployed schema changes.
3. Ensure intended ORM models are imported in `backend/alembic/env.py` before
   generating a migration.
4. Review Alembic autogenerate output, including destructive operations, before applying it.
5. Apply only reviewed migrations to the verified target, as a separate operation.

Never assume a local database is disposable. Databases used with an older scaffold
may still contain a `jobs` table. Do not drop it, reset volumes, or apply destructive
migrations merely to match the current empty scaffold. A new database can be used
for a clean start without deleting the old one.

See [testing conventions](testing.md) for dedicated database test configuration.
