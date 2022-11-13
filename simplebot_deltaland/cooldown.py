"""Cooldown loop logic"""

import random
import time

from simplebot import DeltaBot
from sqlalchemy import func

from .consts import (
    DICE_FEE,
    LIFEREGEN_COOLDOWN,
    MAX_CAULDRON_GIFT,
    MIN_CAULDRON_GIFT,
    STAMINA_COOLDOWN,
    WORLD_ID,
    CombatTactic,
    StateEnum,
)
from .game import (
    get_next_battle_timestamp,
    get_next_day_timestamp,
    get_next_month_timestamp,
    get_next_year_timestamp,
)
from .orm import (
    BattleRank,
    BattleReport,
    CauldronCoin,
    CauldronRank,
    Cooldown,
    DiceRank,
    session_scope,
)
from .quests import get_quest
from .util import get_image, get_players, send_message


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
    if cooldown.id == StateEnum.BATTLE:
        _process_world_battle(session)
        cooldown.ends_at = get_next_battle_timestamp(cooldown.ends_at)
    elif cooldown.id == StateEnum.DAY:
        winner = ""
        gift = session.query(CauldronCoin).count()
        gift = max(MIN_CAULDRON_GIFT, min(MAX_CAULDRON_GIFT, gift))
        for coin in session.query(CauldronCoin).order_by(func.random()):
            player = coin.player
            session.delete(coin)
            send_message(
                bot,
                player.id,
                text=f"✨{winner or 'You'} received {gift}💰 from the magic cauldron✨",
                filename=None if winner else get_image("cauldron"),
            )
            if not winner:
                winner = player.get_name()
                player.gold += gift
                if not player.cauldron_rank:
                    player.cauldron_rank = CauldronRank(gold=0)
                player.cauldron_rank.gold += gift
        cooldown.ends_at = get_next_day_timestamp()
    elif cooldown.id == StateEnum.MONTH:
        session.query(DiceRank).delete()
        session.query(BattleRank).delete()
        cooldown.ends_at = get_next_month_timestamp()
    elif cooldown.id == StateEnum.YEAR:
        session.query(CauldronRank).delete()
        cooldown.ends_at = get_next_year_timestamp()
    else:
        bot.logger.warning(f"Unknown world state: {cooldown.id}")
        session.delete(cooldown)


def _process_world_battle(session) -> None:
    for player in get_players(session):
        victory = False
        monster_tactic = random.choice(list(CombatTactic))
        gold = random.randint((player.level + 1) // 2, player.level + 1)
        hit_points = player.max_hp // 3
        if player.battle_tactic:
            tactic = player.battle_tactic.tactic
            session.delete(player.battle_tactic)
        else:
            tactic = CombatTactic.NONE
        battle = BattleReport(
            tactic=tactic, monster_tactic=monster_tactic, exp=0, gold=0, hp=0
        )
        if tactic == CombatTactic.HIT:
            if monster_tactic == CombatTactic.HIT:
                # TODO: +50% Exp
                battle.hp = -player.reduce_hp(hit_points // 2)  # -50% hit_points
            elif monster_tactic == CombatTactic.FEINT:
                victory = True
                # TODO: +100% Exp
                battle.gold = gold
                player.gold += battle.gold
            else:  # monster_tactic == CombatTactic.PARRY
                # TODO: +25% Exp
                battle.gold = -min(player.gold, gold)
                player.gold += battle.gold
                battle.hp = -player.reduce_hp(hit_points)  # -100% hit_points
        elif tactic == CombatTactic.FEINT:
            if monster_tactic == CombatTactic.HIT:
                # TODO: +25% Exp
                battle.gold = -min(player.gold, gold)
                player.gold += battle.gold
                battle.hp = -player.reduce_hp(hit_points)  # -100% hit_points
            elif monster_tactic == CombatTactic.FEINT:
                # TODO: +50% Exp
                battle.hp = -player.reduce_hp(hit_points // 2)  # -50% hit_points
            else:  # monster_tactic == CombatTactic.PARRY
                victory = True
                # TODO: +100% Exp
                battle.gold = gold
                player.gold += battle.gold
        elif tactic == CombatTactic.PARRY:
            if monster_tactic == CombatTactic.HIT:
                victory = True
                # TODO: +100% Exp
                battle.gold = gold
                player.gold += battle.gold
            elif monster_tactic == CombatTactic.FEINT:
                # TODO: +25% Exp
                battle.gold = -min(player.gold, gold)
                player.gold += battle.gold
                battle.hp = -player.reduce_hp(hit_points)  # -100% hit_points
            else:  # monster_tactic == CombatTactic.PARRY
                pass  # TODO: +25% Exp
        else:  # didn't defend the castle
            battle.gold = -min(player.gold, gold)
            player.gold += battle.gold
            battle.hp = -player.reduce_hp(hit_points)  # -100% hit_points

        player.battle_report = battle
        if victory:
            if not player.battle_rank:
                player.battle_rank = BattleRank(victories=0)
            player.battle_rank += 1


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
    elif cooldown.id == StateEnum.HEALING:
        player = cooldown.player
        player.hp += 1
        if player.hp >= player.max_hp:
            session.delete(cooldown)
        else:
            cooldown.ends_at = cooldown.ends_at + LIFEREGEN_COOLDOWN
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
