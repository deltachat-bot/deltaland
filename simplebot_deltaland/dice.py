"""Dice rolling logic"""

import random
import time
from typing import Tuple

from simplebot.bot import DeltaBot, Replies

from .consts import DICE_COOLDOWN, DICE_FEE, StateEnum
from .orm import Cooldown, Player
from .util import get_name, human_time_duration, send_message

_DICES = {
    1: "⚀",
    2: "⚁",
    3: "⚂",
    4: "⚃",
    5: "⚄",
    6: "⚅",
}


def roll_dice(count: int = 2) -> Tuple[int, ...]:
    return tuple(random.randint(1, 6) for _ in range(count))


def dices2str(dices: Tuple[int, ...]) -> str:
    return " + ".join(_DICES[val] for val in dices) + f" ({sum(dices)})"


def play_dice(player: Player, session, bot: DeltaBot, replies: Replies) -> None:
    player.gold -= DICE_FEE
    player.state = StateEnum.PLAYING_DICE
    cooldown = session.query(Cooldown).filter_by(id=StateEnum.PLAYING_DICE).first()
    if cooldown:
        _play_dice(player, cooldown.player, bot)
        session.delete(cooldown)
    else:
        replies.add(
            text=(
                "You sat down waiting for other players.\n"
                f"If you won't find anyone, you'll leave in {human_time_duration(DICE_COOLDOWN)}"
            )
        )
        session.add(
            Cooldown(
                id=StateEnum.PLAYING_DICE,
                player_id=player.id,
                ends_at=time.time() + DICE_COOLDOWN,
            )
        )


def _play_dice(player1: Player, player2: Player, bot) -> None:
    roll1 = roll_dice()
    roll2 = roll_dice()
    while sum(roll1) == sum(roll2):
        roll1 = roll_dice()
        roll2 = roll_dice()
    if sum(roll1) < sum(roll2):
        player1, player2 = player2, player1
        roll1, roll2 = roll2, roll1

    earned_gold = 2 * DICE_FEE
    player1.gold += earned_gold
    player1.state = player2.state = StateEnum.REST

    name1, name2 = get_name(player1), get_name(player2)
    dices1, dices2 = dices2str(roll1), dices2str(roll2)
    text = "\n".join(
        [
            "🎲 You threw the dice on the table:\n",
            f"{name1}: {dices1}",
            f"{name2}: {dices2}\n",
            f"{name1} won! {earned_gold:+}💰",
        ]
    )
    send_message(bot, player1.id, text=text)
    send_message(bot, player2.id, text=text)
