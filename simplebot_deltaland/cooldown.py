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
from .util import (
    calculate_thieve_gold,
    get_image,
    get_players,
    notify_level_up,
    send_message,
)


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
        _process_world_battle(bot, session)
        cooldown.ends_at = get_next_battle_timestamp(cooldown.ends_at)
    elif cooldown.id == StateEnum.DAY:
        _process_world_cauldron(bot, session)
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


def _process_world_cauldron(bot, session) -> None:
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


def _process_world_battle(bot, session) -> None:
    for player in get_players(session):
        victory = False
        monster_tactic = random.choice(list(CombatTactic))
        gold = random.randint((player.level + 1) // 2, player.level + 1)
        base_exp = random.randint((player.level + 1) // 2, player.level + 1)
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
                battle.exp = max(base_exp // 2, 1)  # +50% Exp
                battle.hp = -player.reduce_hp(hit_points // 2)  # -50% hit_points
            elif monster_tactic == CombatTactic.FEINT:
                victory = True
                battle.exp = base_exp  # +100% Exp
                battle.gold = gold
                player.gold += battle.gold
            else:  # monster_tactic == CombatTactic.PARRY
                battle.exp = max(base_exp // 4, 1)  # +25% Exp
                battle.gold = -min(player.gold, gold)
                player.gold += battle.gold
                battle.hp = -player.reduce_hp(hit_points)  # -100% hit_points
        elif tactic == CombatTactic.FEINT:
            if monster_tactic == CombatTactic.HIT:
                battle.exp = max(base_exp // 4, 1)  # +25% Exp
                battle.gold = -min(player.gold, gold)
                player.gold += battle.gold
                battle.hp = -player.reduce_hp(hit_points)  # -100% hit_points
            elif monster_tactic == CombatTactic.FEINT:
                battle.exp = max(base_exp // 2, 1)  # +50% Exp
                battle.hp = -player.reduce_hp(hit_points // 2)  # -50% hit_points
            else:  # monster_tactic == CombatTactic.PARRY
                victory = True
                battle.exp = base_exp  # +100% Exp
                battle.gold = gold
                player.gold += battle.gold
        elif tactic == CombatTactic.PARRY:
            if monster_tactic == CombatTactic.HIT:
                victory = True
                battle.exp = base_exp  # +100% Exp
                battle.gold = gold
                player.gold += battle.gold
            elif monster_tactic == CombatTactic.FEINT:
                battle.exp = max(base_exp // 4, 1)  # +25% Exp
                battle.gold = -min(player.gold, gold)
                player.gold += battle.gold
                battle.hp = -player.reduce_hp(hit_points)  # -100% hit_points
            else:  # monster_tactic == CombatTactic.PARRY
                battle.exp = max(base_exp // 4, 1)  # +25% Exp
        else:  # didn't defend the castle
            battle.gold = -min(player.gold, gold)
            player.gold += battle.gold
            battle.hp = -player.reduce_hp(hit_points)  # -100% hit_points

        if battle.exp and player.increase_exp(battle.exp):  # level up
            notify_level_up(bot, player)

        player.battle_report = battle
        if victory:
            if not player.battle_rank:
                player.battle_rank = BattleRank(victories=0)
            player.battle_rank.victories += 1


def _process_player_cooldown(bot: DeltaBot, cooldown: Cooldown, session) -> None:
    player = cooldown.player
    if cooldown.id == StateEnum.REST:
        if player.stamina >= player.max_stamina:
            session.delete(cooldown)
            send_message(
                bot,
                player.id,
                text="Stamina restored. You are ready for more adventures!",
            )
        else:
            player.stamina += 1
            cooldown.ends_at = cooldown.ends_at + STAMINA_COOLDOWN
    elif cooldown.id == StateEnum.HEALING:
        if player.hp >= player.max_hp:
            session.delete(cooldown)
        else:
            player.hp += 1
            cooldown.ends_at = cooldown.ends_at + LIFEREGEN_COOLDOWN
    elif cooldown.id == StateEnum.SPOTTED_THIEF:
        thief = player.thief
        gold = calculate_thieve_gold(thief)
        thief.gold += gold
        exp = random.randint(1, 3)
        if thief.increase_exp(exp):  # level up
            notify_level_up(bot, thief)

        text = f"You let **{thief.get_name()}** rob the townsmen. We hope you feel terrible."
        send_message(bot, player.id, text=text)

        text = (
            f"**{player.get_name()}** was completely clueless. You successfully stole some loot."
            " You feel great.\n\n"
            f"💰Gold: {gold:+}\n"
            f"🔥Exp: {exp:+}\n"
        )
        send_message(bot, thief.id, text=text)
        player.stop_spotting()  # removes cooldown from session
    elif cooldown.id == StateEnum.PLAYING_DICE:
        session.delete(cooldown)
        player.state = StateEnum.REST
        player.gold += DICE_FEE
        send_message(bot, player.id, text="No one sat down next to you =/")
    else:
        quest = get_quest(cooldown.id)
        if quest:
            quest.end(bot, cooldown, session)
        else:
            bot.logger.warning(f"Unknown quest: {cooldown.id}")
        session.delete(cooldown)
