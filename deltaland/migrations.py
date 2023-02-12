"""Database migrations"""
import logging
import os
import sqlite3
import time

from .consts import DATABASE_VERSION, STARTING_INV_SIZE


def run_migrations(dbpath: str) -> None:
    if not os.path.exists(dbpath):
        logging.debug("Database doesn't exists, skipping migrations")
        return

    database = sqlite3.connect(dbpath)
    database.row_factory = sqlite3.Row
    try:
        version = database.execute("SELECT * FROM game").fetchone()["version"]
        logging.debug("Current database version: v%s", version)
        for i in range(version + 1, DATABASE_VERSION + 1):
            migration = globals().get(f"migrate{i}")
            assert migration
            logging.info("Migrating database: v%s", i)
            with database:
                database.execute("UPDATE game SET version=?", (i,))
                migration(database)
    finally:
        database.close()


def migrate5(database: sqlite3.Connection) -> None:
    database.execute(
        f"ALTER TABLE player ADD COLUMN inv_size INTEGER DEFAULT {STARTING_INV_SIZE}"
    )


def migrate6(database: sqlite3.Connection) -> None:
    now = int(time.time())
    database.execute(f"ALTER TABLE player ADD COLUMN last_seen INTEGER DEFAULT {now}")
    database.execute("UPDATE player SET last_seen=0 WHERE id=0")
