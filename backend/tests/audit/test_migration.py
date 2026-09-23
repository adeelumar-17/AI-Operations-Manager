from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect


def test_migration_handles_fresh_metadata_and_existing_schema(database):
    # Local alembic directory intentionally has no __init__; load the revision by path.
    import importlib.util
    spec = importlib.util.spec_from_file_location('audit_revision', 'alembic/versions/004_followup_claims_and_query_indexes.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with database.kw['bind'].begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        migration.upgrade()
        assert 'ix_followup_due' in {index['name'] for index in inspect(conn).get_indexes('followup_tasks')}
        migration.downgrade()
        assert 'started_at' not in {column['name'] for column in inspect(conn).get_columns('followup_tasks')}
        migration.upgrade()
        assert 'started_at' in {column['name'] for column in inspect(conn).get_columns('followup_tasks')}
