"""Utilities"""
import os
import random
import string
import time
from typing import Optional

from deltachat import Message
from simplebot.bot import DeltaBot, Replies

from .consts import WORLD_ID, CombatTactic, StateEnum
from .orm import Cooldown, Player

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


def validate_resting(
    player: Player, replies: Replies, session, ignore_battle: bool = False
) -> bool:
    if not ignore_battle:
        remaining_time = (
            session.query(Cooldown)
            .filter_by(id=StateEnum.BATTLE, player_id=WORLD_ID)
            .first()
        ).ends_at - time.time()
        if remaining_time < 60 * 11:
            replies.add(text="Gobling battle is coming. You have no time for games.")
            return False

    if player.state == StateEnum.REST:
        return True

    replies.add(text="You are too busy with a different adventure. Try a bit later.")
    return False


def validate_level(player: Player, required_level: int, replies: Replies) -> bool:
    if player.level >= required_level:
        return True
    replies.add(text="🍼 Your level is too low to perform that action.")
    return False


def validate_gold(player: Player, required_gold: int, replies: Replies) -> bool:
    if player.gold >= required_gold:
        return True
    replies.add(
        text="You don't even have enough gold for a pint of grog.\nWhy don't you get a job?"
    )
    return False


def validate_stamina(player: Player, required_stamina: int, replies: Replies) -> bool:
    if player.stamina >= required_stamina:
        return True
    replies.add(text="Not enough stamina. Come back after you take a rest.")
    return False


def validate_hp(player: Player, replies: Replies) -> bool:
    if player.hp >= 100:
        return True
    replies.add(text="You need to heal your wounds and recover, come back later.")
    return False


def get_image(name: str) -> str:
    return os.path.join(_images_dir, f"{name}.webp")


def get_database_path(bot: DeltaBot) -> str:
    path = os.path.join(os.path.dirname(bot.account.db_path), _scope)
    if not os.path.exists(path):
        os.makedirs(path)
    return os.path.join(path, "sqlite.db")


def calculate_thieve_gold(player: Player) -> int:
    min_gold = min(max(player.level, 10), 20)
    return random.randint(min_gold, min(min_gold * 3, 40))


def calculate_interfere_gold(player: Player) -> int:
    min_gold = min(max(player.level, 5), 10)
    return random.randint(min_gold, min_gold * 2)


def notify_level_up(bot: DeltaBot, player: Player) -> None:
    text = f"🎉 Congratulations! You reached level {player.level}!\n"
    if player.level == 2:
        text += (
            "The higher the level, the more activities become available to you.\n"
            "- Thieve quests are available at level 3.\n"
            "- World leaderboards are available at level 3."
        )
    elif player.level == 3:
        text += "- New quest Thieve unlocked!\n- You can learn how other players are doing via the leaderboards at /top"
        text += (
            "\n\n**WARNING:** Work in progress, level 3 is the maximum level for now."
        )
    send_message(bot, player.id, text=text, filename=get_image("level-up"))


def get_battle_result(player: Player) -> str:
    battle = player.battle_report
    tie_msg = (
        "You both avoided each other's attacks."
        " The goblin was surprised by this outcome and ran away."
    )
    tie_damage_msg = (
        "You exchanged blows."
        " The wounded goblin fled as fast as he could, you fainted shortly after."
    )
    win_msg = "You killed the goblin. On his cold corpse you found some gold."
    lose_msg = "The blow was so strong that you fainted."
    if battle.gold:
        lose_msg += " The goblin took as much gold as he could before other warriors could aid you."
    else:
        lose_msg += " The goblin was disappointed to see you didn't have a single gold coin in your pocket"
    hit_result = "{loser} feints but is defeated by {winner}'s hit!"
    feint_result = "{loser} tries to parry, but {winner} feints and hits!"
    parry_result = "{loser} tries to hit {winner}, but {winner} parries the attack and counterattacks!"
    monster_name = "the goblin"
    player_name = player.get_name()
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
        f" one of them is quickly running towards {player_name}.\n\n"
        f"{text}{stats}"
    )
