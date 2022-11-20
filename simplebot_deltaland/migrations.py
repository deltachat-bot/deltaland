"""Database migrations"""
import os
import sqlite3
from logging import Logger

from simplebot.bot import DeltaBot

from .consts import DATABASE_VERSION, STARTING_INV_SIZE
from .util import get_database_path


def run_migrations(bot: DeltaBot) -> None:
    path = get_database_path(bot)
    if not os.path.exists(path):
        bot.logger.debug("Database doesn't exists, skipping migrations")
        return

    database = sqlite3.connect(path)
    database.row_factory = sqlite3.Row
    try:
        version = database.execute("SELECT * FROM game").fetchone()["version"]
        bot.logger.debug(f"Current database version: v{version}")
        for i in range(5, DATABASE_VERSION + 1):
            if version >= i:
                continue
            migration = globals().get(f"migrate{i}")
            assert migration
            migration(database, bot.logger)
    finally:
        database.close()


def migrate5(database: sqlite3.Connection, logger: Logger) -> None:
    new_version = 5
    logger.info(f"Migrating database: v{new_version}")
    with database:
        database.execute("UPDATE game SET version=?", (new_version,))
        database.execute(
            f"ALTER TABLE player ADD COLUMN  inv_size INTEGER DEFAULT {STARTING_INV_SIZE}"
        )
