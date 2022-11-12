"""Game global state logic"""
import time
from datetime import datetime, timedelta

from .consts import DATABASE_VERSION, WORLD_ID, StateEnum
from .orm import Cooldown, Game, Player, session_scope
from .util import human_time_duration


def init_game() -> None:
    with session_scope() as session:
        if not session.query(Game).first():
            session.add(Game(version=DATABASE_VERSION))

        world = session.query(Player).filter_by(id=WORLD_ID).first()
        if not world:
            world = Player(id=WORLD_ID, birthday=time.time())
            session.add(world)

        if (
            not session.query(Cooldown)
            .filter_by(id=StateEnum.YEAR, player_id=world.id)
            .first()
        ):
            world.cooldowns.append(
                Cooldown(id=StateEnum.YEAR, ends_at=get_next_year_timestamp())
            )

        if (
            not session.query(Cooldown)
            .filter_by(id=StateEnum.MONTH, player_id=world.id)
            .first()
        ):
            world.cooldowns.append(
                Cooldown(id=StateEnum.MONTH, ends_at=get_next_month_timestamp())
            )

        if (
            not session.query(Cooldown)
            .filter_by(id=StateEnum.DAY, player_id=world.id)
            .first()
        ):
            world.cooldowns.append(
                Cooldown(id=StateEnum.DAY, ends_at=get_next_day_timestamp())
            )

        if (
            not session.query(Cooldown)
            .filter_by(id=StateEnum.BATTLE, player_id=world.id)
            .first()
        ):
            last_battle = int(
                datetime.today().replace(minute=0, second=0, microsecond=0).timestamp()
            )
            world.cooldowns.append(
                Cooldown(
                    id=StateEnum.BATTLE, ends_at=get_next_battle_timestamp(last_battle)
                )
            )


def get_next_year_timestamp() -> int:
    return int(
        (datetime.today().replace(day=31, month=12) + timedelta(days=1))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .timestamp()
    )


def get_next_month_timestamp() -> int:
    return int(
        (datetime.today().replace(day=25) + timedelta(days=7))
        .replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        .timestamp()
    )


def get_next_day_timestamp() -> int:
    return int(
        (datetime.today() + timedelta(days=1))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .timestamp()
    )


def get_next_battle_timestamp(last_battle: int) -> int:
    return int((datetime.fromtimestamp(last_battle) + timedelta(hours=8)).timestamp())


def get_next_day_cooldown(session) -> str:
    remaining_time = (
        session.query(Cooldown).filter_by(id=StateEnum.DAY, player_id=WORLD_ID).first()
    ).ends_at - time.time()
    return human_time_duration(remaining_time)
