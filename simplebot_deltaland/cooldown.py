"""Cooldown loop logic"""

import time

from simplebot import DeltaBot
from sqlalchemy import func

from .consts import (
    DICE_FEE,
    MAX_CAULDRON_GIFT,
    MIN_CAULDRON_GIFT,
    STAMINA_COOLDOWN,
    WORLD_ID,
    StateEnum,
)
from .game import (
    get_next_day_timestamp,
    get_next_month_timestamp,
    get_next_year_timestamp,
)
from .orm import CauldronRank, Cooldown, DiceRank, session_scope
from .quests import get_quest
from .util import get_image, get_name, get_players, send_message


def cooldown_loop(bot: DeltaBot) -> None:
    while True:
        try:
            _check_cooldows(bot)
        except Exception as ex:
            bot.logger.exception(ex)
        time.sleep(1)


def _check_cooldows(bot: DeltaBot) -> None:
    with session_scope() as session:
        query = (
            session.query(Cooldown)
            .filter(Cooldown.ends_at <= time.time())
            .order_by(Cooldown.ends_at)
        )
        for cooldown in query:
            try:
                if cooldown.player_id == WORLD_ID:
                    _process_world_cooldown(bot, cooldown, session)
                else:
                    _process_player_cooldown(bot, cooldown, session)
            except Exception as ex:
                bot.logger.exception(ex)


def _process_world_cooldown(bot: DeltaBot, cooldown: Cooldown, session) -> None:
    if cooldown.id == StateEnum.DAY:
        winner = ""
        gift = get_players(session).filter_by(cauldron_coin=1).count()
        gift = max(MIN_CAULDRON_GIFT, min(MAX_CAULDRON_GIFT, gift))
        for player in (
            get_players(session).filter_by(cauldron_coin=1).order_by(func.random())
        ):
            player.cauldron_coin = 0
            send_message(
                bot,
                player.id,
                text=f"✨{winner or 'You'} received {gift}💰 from the magic cauldron✨",
                filename=None if winner else get_image("cauldron"),
            )
            if not winner:
                winner = get_name(player)
                player.gold += gift
        cooldown.ends_at = get_next_day_timestamp()
    elif cooldown.id == StateEnum.MONTH:
        session.query(DiceRank).delete()
        cooldown.ends_at = get_next_month_timestamp()
    elif cooldown.id == StateEnum.YEAR:
        session.query(CauldronRank).delete()
        cooldown.ends_at = get_next_year_timestamp()
    else:
        bot.logger.warning(f"Unknown world state: {cooldown.id}")
        session.delete(cooldown)


def _process_player_cooldown(bot: DeltaBot, cooldown: Cooldown, session) -> None:
    if cooldown.id == StateEnum.REST:
        player = cooldown.player
        player.stamina += 1
        if player.stamina >= player.max_stamina:
            session.delete(cooldown)
            send_message(
                bot,
                player.id,
                text="Stamina restored. You are ready for more adventures!",
            )
        else:
            cooldown.ends_at = cooldown.ends_at + STAMINA_COOLDOWN
    elif cooldown.id == StateEnum.PLAYING_DICE:
        player = cooldown.player
        session.delete(cooldown)
        player.state = StateEnum.REST
        player.gold += DICE_FEE
        send_message(bot, player.id, text="No one sat down next to you =/")
    else:
        _process_quest_cooldown(bot, cooldown, session)


def _process_quest_cooldown(bot: DeltaBot, cooldown: Cooldown, session) -> None:
    quest = get_quest(cooldown.id)
    if quest:
        player = cooldown.player
        reward = quest.get_reward(player)
        text = reward.description
        if reward.gold:
            text += f"\n\nYou received: {reward.gold:+}💰"
            player.gold += reward.gold
        player.state = StateEnum.REST
        send_message(bot, cooldown.player_id, text=text)
    else:
        bot.logger.warning(f"Unknown quest: {cooldown.id}")
    session.delete(cooldown)
