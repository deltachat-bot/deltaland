"""Utilities"""

import os
import string
from typing import Optional

from deltachat import Message
from simplebot.bot import DeltaBot, Replies

from .consts import StateEnum
from .orm import Player

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


def get_name(player: Player) -> str:
    return player.name if player.name else f"Player{player.id}"


def get_player(session, message: Message, replies: Replies) -> Optional[Player]:
    """Get the player corresponding to a message.

    An error message is sent if the user have not joined the game yet
    """
    player_id = message.get_sender_contact().id
    player = session.query(Player).filter_by(id=player_id).first()
    if player:
        return player
    replies.add(text="❌ You have not joined the game yet, send /start")
    return None


def get_players(session):
    return session.query(Player).filter(Player.id > 0)


def validate_resting(player: Player, replies: Replies) -> bool:
    if player.state == StateEnum.REST:
        return True
    replies.add(text="You are too busy with a different adventure. Try a bit later.")
    return False


def validate_gold(player: Player, required_gold: int, replies: Replies) -> bool:
    if player.gold >= required_gold:
        return True
    replies.add(
        text="You don't even have enough gold for a pint of grog.\nWhy don't you get a job?"
    )
    return False


def get_image(name: str) -> str:
    return os.path.join(_images_dir, f"{name}.webp")
