"""Utilities"""
import os
import random
import string
from typing import Optional

from simplebot.bot import DeltaBot, Replies

_scope = __name__.split(".", maxsplit=1)[0]
_images_dir = os.path.join(os.path.dirname(__file__), "images")
_TIME_DURATION_UNITS = (
    ("week", 60 * 60 * 24 * 7),
    ("day", 60 * 60 * 24),
    ("hour", 60 * 60),
    ("min", 60),
    ("sec", 1),
)


def setdefault(bot: DeltaBot, key: str, value: Optional[str] = None) -> str:
    val = bot.get(key, scope=_scope)
    if val is None and value is not None:
        bot.set(key, value, scope=_scope)
        val = value
    return val


def is_valid_name(name: str) -> bool:
    valid_chars = string.ascii_letters + string.digits + " "
    for char in name:
        if char not in valid_chars:
            return False

    return 0 < len(name) <= 16


def send_message(bot: DeltaBot, player_id: int, **kwargs) -> None:
    try:
        replies = Replies(bot, bot.logger)
        chat = bot.account.get_contact_by_id(player_id).create_chat()
        replies.add(**kwargs, chat=chat)
        replies.send_reply_messages()
    except Exception as ex:
        bot.logger.exception(ex)


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


def get_database_path(bot: DeltaBot) -> str:
    path = os.path.join(os.path.dirname(bot.account.db_path), _scope)
    if not os.path.exists(path):
        os.makedirs(path)
    return os.path.join(path, "sqlite.db")


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
