"""Game global state logic"""
import time
from datetime import datetime, timedelta

from sqlalchemy.future import select

from .consts import DATABASE_VERSION, WORLD_ID, StateEnum
from .items import init_items
from .orm import Cooldown, Game, Player, async_session, fetchone
from .skills import init_skills
from .util import human_time_duration


async def init_game() -> None:
    async with async_session() as session:
        async with session.begin():
            if not await fetchone(session, select(Game)):
                session.add(Game(version=DATABASE_VERSION))

            await init_items(session)
            await init_skills(session)

            world = await fetchone(session, select(Player).filter_by(id=WORLD_ID))
            if not world:
                world = Player(id=WORLD_ID, last_seen=0)
                session.add(world)

            if not await fetchone(
                session,
                select(Cooldown).filter_by(id=StateEnum.YEAR, player_id=world.id),
            ):
                session.add(
                    Cooldown(
                        id=StateEnum.YEAR,
                        player_id=world.id,
                        ends_at=get_next_year_timestamp(),
                    )
                )

            if not await fetchone(
                session,
                select(Cooldown).filter_by(id=StateEnum.MONTH, player_id=world.id),
            ):
                session.add(
                    Cooldown(
                        id=StateEnum.MONTH,
                        player_id=world.id,
                        ends_at=get_next_month_timestamp(),
                    )
                )

            if not await fetchone(
                session,
                select(Cooldown).filter_by(id=StateEnum.DAY, player_id=world.id),
            ):
                session.add(
                    Cooldown(
                        id=StateEnum.DAY,
                        player_id=world.id,
                        ends_at=get_next_day_timestamp(),
                    )
                )

            if not await fetchone(
                session,
                select(Cooldown).filter_by(id=StateEnum.BATTLE, player_id=world.id),
            ):
                last_battle = int(
                    datetime.today()
                    .replace(minute=0, second=0, microsecond=0)
                    .timestamp()
                )
                session.add(
                    Cooldown(
                        id=StateEnum.BATTLE,
                        player_id=world.id,
                        ends_at=get_next_battle_timestamp(last_battle),
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


async def get_next_battle_cooldown(session) -> str:
    stmt = select(Cooldown).filter_by(id=StateEnum.BATTLE, player_id=WORLD_ID)
    remaining_time = (await fetchone(session, stmt)).ends_at - time.time()
    return human_time_duration(remaining_time)


async def get_next_day_cooldown(session) -> str:
    stmt = select(Cooldown).filter_by(id=StateEnum.DAY, player_id=WORLD_ID)
    remaining_time = (await fetchone(session, stmt)).ends_at - time.time()
    return human_time_duration(remaining_time)
