"""Utilities"""
import asyncio
import logging
import os
import random
import string
from typing import Coroutine, Union

from deltachat_rpc_client.rpc import JsonRpcError
from simplebot_aio import Account, Contact

_scope = __name__.split(".", maxsplit=1)[0]
_images_dir = os.path.join(os.path.dirname(__file__), "images")
_TIME_DURATION_UNITS = (
    ("week", 60 * 60 * 24 * 7),
    ("day", 60 * 60 * 24),
    ("hour", 60 * 60),
    ("min", 60),
    ("sec", 1),
)
_background_tasks = set()


def run_in_background(coro: Coroutine) -> None:
    """Schedule the execution of a coroutine object in a spawn task, keeping a
    reference to the task to avoid it disappearing mid-execution due to GC.
    """
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def is_valid_name(name: str) -> bool:
    valid_chars = string.ascii_letters + string.digits + " "
    for char in name:
        if char not in valid_chars:
            return False

    return 0 < len(name) <= 16


async def send_message(
    contact: Union[int, Contact], account: Account = None, **kwargs
) -> None:
    if isinstance(contact, int):
        contact = account.get_contact_by_id(contact)
    try:
        await (await contact.create_chat()).send_message(**kwargs)
    except JsonRpcError as err:
        logging.exception(err)


def human_time_duration(seconds: int, rounded: bool = True) -> str:
    if seconds < 60:
        return "a few seconds"
    parts = []
    for unit, div in _TIME_DURATION_UNITS:
        amount, seconds = divmod(int(seconds), div)
        if amount > 0:
            plural = "s" if amount > 1 and unit not in ["min", "sec"] else ""
            parts.append(f"{amount}{unit}{plural}")
            if rounded and unit == "min":
                break
    return ", ".join(parts)


def get_image(name: str) -> str:
    return os.path.join(_images_dir, f"{name}.webp")


def render_stats(atk: int, def_: int) -> str:
    stats = "".join(
        [
            e
            for e in [
                f"{atk:+}⚔️" if atk else "",
                f"{def_:+}🛡️" if def_ else "",
            ]
            if e
        ]
    )
    return stats


def calculate_thieve_gold(level: int) -> int:
    min_gold = min(max(level, 10), 20)
    return random.randint(min_gold, min(min_gold * 3, 40))


def calculate_interfere_gold(level: int) -> int:
    min_gold = min(max(level, 5), 10)
    return random.randint(min_gold, min_gold * 2)
