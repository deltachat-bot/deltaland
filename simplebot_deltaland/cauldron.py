"""Cauldron logic"""
import time
from datetime import datetime, timedelta

from .consts import WORLD_ID, StateEnum
from .orm import Cooldown
from .util import human_time_duration


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
