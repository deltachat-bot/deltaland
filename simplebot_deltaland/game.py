"""Game global state logic"""
import time
from datetime import datetime, timedelta

from .consts import WORLD_ID, StateEnum
from .orm import Cooldown, Game, Player, session_scope
from .util import human_time_duration


def init_game() -> None:
    with session_scope() as session:
        if not session.query(Game).first():
            session.add(Game(version=1))

        if not session.query(Player).filter_by(id=WORLD_ID).first():
            session.add(Player(id=WORLD_ID, birthday=time.time()))

        if (
            not session.query(Cooldown)
            .filter_by(id=StateEnum.RANKING, player_id=WORLD_ID)
            .first()
        ):
            session.add(
                Cooldown(
                    id=StateEnum.RANKING,
                    player_id=WORLD_ID,
                    ends_at=get_next_ranking_event(),
                )
            )

        if (
            not session.query(Cooldown)
            .filter_by(id=StateEnum.CAULDRON, player_id=WORLD_ID)
            .first()
        ):
            session.add(
                Cooldown(
                    id=StateEnum.CAULDRON,
                    player_id=WORLD_ID,
                    ends_at=get_next_cauldron_event(),
                )
            )


def get_next_ranking_event() -> int:
    return int(
        (datetime.today().replace(day=25) + timedelta(days=7))
        .replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        .timestamp()
    )


def get_next_cauldron_event() -> int:
    return int(
        (datetime.today() + timedelta(days=1))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .timestamp()
    )


def get_cauldron_cooldown(session) -> str:
    remaining_time = (
        session.query(Cooldown)
        .filter_by(id=StateEnum.CAULDRON, player_id=WORLD_ID)
        .first()
    ).ends_at - time.time()
    return human_time_duration(remaining_time)
