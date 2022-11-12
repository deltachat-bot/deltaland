"""Database migrations"""
import os
import sqlite3
from logging import Logger

from simplebot.bot import DeltaBot

from .consts import DATABASE_VERSION
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
        for i in range(2, DATABASE_VERSION + 1):
            migration = globals().get(f"migrate{i}")
            assert migration
            migration(version, database, bot.logger)
    finally:
        database.close()


def migrate2(version: int, database: sqlite3.Connection, logger: Logger) -> None:
    if version < 2:
        logger.info("Migrating database: v2")
        with database:
            database.execute("UPDATE game SET version=?", (2,))
            database.execute("UPDATE player SET attack=1, defense=1")
            database.execute(
                """CREATE TABLE IF NOT EXISTS cauldroncoin (
	        id INTEGER NOT NULL,
	        PRIMARY KEY (id),
	        FOREIGN KEY(id) REFERENCES player (id)
                )"""
            )
            for player in database.execute(
                "SELECT * FROM player WHERE cauldron_coin=1"
            ):
                database.execute(
                    "REPLACE INTO cauldroncoin VALUES (?)", (player["id"],)
                )
            database.execute(
                """CREATE TABLE player2 (
                    id INTEGER NOT NULL,
                    name VARCHAR(100),
                    birthday INTEGER,
                    level INTEGER,
                    exp INTEGER,
                    attack INTEGER,
                    defense INTEGER,
                    hp INTEGER,
                    max_hp INTEGER,
                    mana INTEGER,
                    max_mana INTEGER,
                    stamina INTEGER,
                    max_stamina INTEGER,
                    gold INTEGER,
                    state INTEGER,
                    PRIMARY KEY (id)
                )"""
            )
            database.execute(
                "INSERT INTO player2 SELECT id, name, birthday, level, exp, attack, defense,hp, max_hp, mana, max_mana, stamina, max_stamina, gold, state FROM player"
            )
            database.execute("DROP TABLE player")
            database.execute("ALTER TABLE player2 RENAME TO player")

            # due to bug in v1, cauldronrank table need to be cleaned up
            database.execute("DELETE FROM cauldronrank WHERE gold=0")
