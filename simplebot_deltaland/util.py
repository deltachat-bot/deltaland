"""Utilities"""

import os
import string
from typing import Optional

from deltachat import Message
from simplebot.bot import DeltaBot, Replies

from .consts import CombatTactic, StateEnum
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


def get_database_path(bot: DeltaBot) -> str:
    path = os.path.join(os.path.dirname(bot.account.db_path), _scope)
    if not os.path.exists(path):
        os.makedirs(path)
    return os.path.join(path, "sqlite.db")


def get_battle_result(player: Player) -> str:
    tie_msg = (
        "You both avoided each other's attacks."
        " The goblin was surprised by this outcome and ran away."
    )
    tie_damage_msg = (
        "You exchanged blows."
        " The wounded goblin fled as fast as he could, you fainted shortly after."
    )
    win_msg = "You killed the goblin. On his cold corpse you found some gold."
    lose_msg = (
        "This is sad, but you're nearly dead."
        " The goblin took as much gold as he could before other warriors could aid you."
    )
    hit_result = "{loser} feints but is defeated by {winner}'s hit!"
    feint_result = "{loser} tries to parry, but {winner} feints and hits!"
    parry_result = "{loser} tries to hit {winner}, but {winner} parries the attack and counterattacks!"
    monster_name = "the goblin"
    player_name = player.get_name()
    battle = player.battle_report
    monster_tactic = battle.monster_tactic
    tactic = battle.tactic
    if tactic == CombatTactic.HIT:
        if monster_tactic == CombatTactic.HIT:
            text = tie_damage_msg
        elif monster_tactic == CombatTactic.FEINT:
            result = hit_result.format(winner=player_name, loser=monster_name)
            text = f"{result}\n{win_msg}"
        else:  # monster_tactic == CombatTactic.PARRY
            result = parry_result.format(winner=monster_name, loser=player_name)
            text = f"{result}\n{lose_msg}"
    elif tactic == CombatTactic.FEINT:
        if monster_tactic == CombatTactic.HIT:
            result = hit_result.format(winner=monster_name, loser=player_name)
            text = f"{result}\n{lose_msg}"
        elif monster_tactic == CombatTactic.FEINT:
            text = tie_damage_msg
        else:  # monster_tactic == CombatTactic.PARRY
            result = feint_result.format(winner=player_name, loser=monster_name)
            text = f"{result}\n{win_msg}"
    elif tactic == CombatTactic.PARRY:
        if monster_tactic == CombatTactic.HIT:
            result = parry_result.format(winner=player_name, loser=monster_name)
            text = f"{result}\n{win_msg}"
        elif monster_tactic == CombatTactic.FEINT:
            result = feint_result.format(winner=monster_name, loser=player_name)
            text = f"{result}\n{lose_msg}"
        else:  # monster_tactic == CombatTactic.PARRY
            text = tie_msg
    else:  # not parting on battle
        text = f"{player_name} was petrified by the fear and could't avoid {monster_name}'s attack.\n{lose_msg}"

    stats = "\n\n"
    if battle.exp:
        stats += f"🔥Exp: {battle.exp:+}\n"
    if battle.gold:
        stats += f"💰Gold: {battle.gold:+}\n"
    if battle.hp:
        stats += f"❤️HP: {battle.hp:+}\n"
    return (
        f"{player_name} 🏅{player.level}\n"
        "Your result on the battlefield:\n\n"
        "The goblins started to attack the castle,"
        f" one of them is quickly running towards {player_name}.\n"
        f"{text}{stats}"
    )
