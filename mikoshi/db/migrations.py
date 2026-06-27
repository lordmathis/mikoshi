import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def run_migrations(engine):
    with engine.connect() as conn:
        _migrate_file_ids_column(conn)
        _migrate_drop_file_attachments_table(conn)
        _migrate_tool_call_id_column(conn)
        _migrate_file_source_column(conn)
        _migrate_chat_workspace_id_column(conn)
        _migrate_workspace_repo_url_nullable(conn)
        conn.commit()


def _migrate_file_ids_column(conn):
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("messages")]

    if "file_ids" not in columns:
        logger.info("Adding file_ids column to messages table...")
        conn.execute(text("ALTER TABLE messages ADD COLUMN file_ids TEXT"))
        logger.info("Column file_ids added to messages table.")
    else:
        logger.debug("Column file_ids already exists in messages table.")


def _migrate_drop_file_attachments_table(conn):
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if "file_attachments" in tables:
        logger.info("Dropping file_attachments table...")
        conn.execute(text("DROP TABLE file_attachments"))
        logger.info("Table file_attachments dropped.")
    else:
        logger.debug("Table file_attachments does not exist.")


def _migrate_tool_call_id_column(conn):
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("messages")]

    if "tool_call_id" not in columns:
        logger.info("Adding tool_call_id column to messages table...")
        conn.execute(text("ALTER TABLE messages ADD COLUMN tool_call_id TEXT"))
        logger.info("Column tool_call_id added to messages table.")
    else:
        logger.debug("Column tool_call_id already exists in messages table.")


def _migrate_file_source_column(conn):
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("files")]

    if "source" not in columns:
        logger.info("Adding source column to files table...")
        conn.execute(text("ALTER TABLE files ADD COLUMN source TEXT"))
        logger.info("Column source added to files table.")
    else:
        logger.debug("Column source already exists in files table.")


def _migrate_chat_workspace_id_column(conn):
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("chats")]

    if "workspace_id" not in columns:
        logger.info("Adding workspace_id column to chats table...")
        conn.execute(
            text(
                "ALTER TABLE chats ADD COLUMN workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL"
            )
        )
        logger.info("Column workspace_id added to chats table.")
    else:
        logger.debug("Column workspace_id already exists in chats table.")


def _migrate_workspace_repo_url_nullable(conn):
    inspector = inspect(conn)

    tables = inspector.get_table_names()
    if "workspaces" not in tables:
        return

    columns = [col for col in inspector.get_columns("workspaces")]
    repo_url_col = next((c for c in columns if c["name"] == "repo_url"), None)
    if repo_url_col is None or repo_url_col.get("nullable", True):
        logger.debug("Column repo_url already nullable (or absent) in workspaces table.")
        return

    logger.info("Making workspaces.repo_url nullable...")
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(
        text(
            """
            CREATE TABLE _workspaces_new (
                id VARCHAR PRIMARY KEY,
                name VARCHAR,
                repo_url VARCHAR,
                local_path VARCHAR,
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
                (id, name, repo_url, local_path, connector, created_at, updated_at)
            SELECT id, name, repo_url, local_path, connector, created_at, updated_at
            FROM workspaces
            """
        )
    )
    conn.execute(text("DROP TABLE workspaces"))
    conn.execute(text("ALTER TABLE _workspaces_new RENAME TO workspaces"))
    conn.execute(text("PRAGMA foreign_keys=ON"))
    logger.info("Column repo_url is now nullable in workspaces table.")
