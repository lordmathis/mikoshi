import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def run_migrations(engine):
    with engine.connect() as conn:
        _add_column_if_missing(conn, "messages", "file_ids", "file_ids TEXT")
        _drop_table_if_exists(conn, "file_attachments")
        _add_column_if_missing(conn, "messages", "tool_call_id", "tool_call_id TEXT")
        _add_column_if_missing(conn, "files", "source", "source TEXT")
        _add_column_if_missing(
            conn,
            "chats",
            "workspace_id",
            "workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL",
        )
        _migrate_workspace_repo_url_nullable(conn)
        _add_column_if_missing(
            conn, "workspaces", "default_agent", "default_agent TEXT"
        )
        _add_column_if_missing(conn, "chats", "skills", "skills TEXT")
        _add_column_if_missing(conn, "messages", "phase", "phase TEXT")
        _drop_column_if_exists(conn, "workspaces", "local_path")
        conn.commit()


def _add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    names = {c["name"] for c in inspect(conn).get_columns(table)}
    if column not in names:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
        logger.info("Added %s.%s", table, column)


def _drop_column_if_exists(conn, table: str, column: str) -> None:
    names = {c["name"] for c in inspect(conn).get_columns(table)}
    if column in names:
        conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))
        logger.info("Dropped %s.%s", table, column)


def _drop_table_if_exists(conn, table: str) -> None:
    if table in inspect(conn).get_table_names():
        conn.execute(text(f"DROP TABLE {table}"))
        logger.info("Dropped table %s", table)


def _migrate_workspace_repo_url_nullable(conn):
    inspector = inspect(conn)

    tables = inspector.get_table_names()
    if "workspaces" not in tables:
        return

    columns = [col for col in inspector.get_columns("workspaces")]
    repo_url_col = next((c for c in columns if c["name"] == "repo_url"), None)
    if repo_url_col is None or repo_url_col.get("nullable", True):
        return

    # Pre-nullable-era rebuild: old DBs made repo_url NOT NULL, which SQLite
    # can only change via table rebuild. local_path is dropped here too —
    # the column is dead and must not survive the rebuild.
    logger.info("Making workspaces.repo_url nullable...")
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(
        text(
            """
            CREATE TABLE _workspaces_new (
                id VARCHAR PRIMARY KEY,
                name VARCHAR,
                repo_url VARCHAR,
                connector VARCHAR,
                created_at DATETIME,
                updated_at DATETIME
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO _workspaces_new
                (id, name, repo_url, connector, created_at, updated_at)
            SELECT id, name, repo_url, connector, created_at, updated_at
            FROM workspaces
            """
        )
    )
    conn.execute(text("DROP TABLE workspaces"))
    conn.execute(text("ALTER TABLE _workspaces_new RENAME TO workspaces"))
    conn.execute(text("PRAGMA foreign_keys=ON"))
    logger.info("Column repo_url is now nullable in workspaces table.")
