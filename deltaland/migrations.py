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


def migrate7(database: sqlite3.Connection) -> None:
    database.execute("UPDATE player SET hp=40, max_hp=40")

    # add skill_points
    database.execute("ALTER TABLE player ADD COLUMN skill_points INTEGER")
    database.execute("UPDATE player SET skill_points=player.level-1")

    # add shop_price column to BaseItem
    database.execute("ALTER TABLE baseitem ADD COLUMN shop_price INTEGER")

    # add max_attack/max_defense
    database.execute("ALTER TABLE player ADD COLUMN max_attack INTEGER")
    database.execute("ALTER TABLE player ADD COLUMN max_defense INTEGER")
    database.execute(
        "UPDATE player SET max_attack=player.attack, max_defense=player.defense"
    )
    database.execute("ALTER TABLE baseitem ADD COLUMN max_attack INTEGER")
    database.execute("ALTER TABLE baseitem ADD COLUMN max_defense INTEGER")
    database.execute("ALTER TABLE item ADD COLUMN max_attack INTEGER")
    database.execute("ALTER TABLE item ADD COLUMN max_defense INTEGER")
    database.execute("UPDATE item SET max_attack=5 WHERE base_id=1")
    database.execute("UPDATE item SET max_defense=3 WHERE base_id=2")
    database.execute("UPDATE item SET defense=2 WHERE base_id=2")
