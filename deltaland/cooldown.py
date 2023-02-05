"""Cooldown loop logic"""
import asyncio
import logging
import random
import time

from sqlalchemy import func
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import delete

from .consts import (
    CAULDRON_GIFT,
    DICE_FEE,
    LIFEREGEN_COOLDOWN,
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
    BattleTactic,
    CauldronCoin,
    CauldronRank,
    Cooldown,
    DiceRank,
    Player,
    async_session,
    fetchone,
)
from .quests import get_quest
from .util import calculate_thieve_gold, get_image


async def cooldown_loop() -> None:
    while True:
        try:
            await _check_cooldows()
        except Exception as ex:
            logging.exception(ex)
        await asyncio.sleep(1)


async def _check_cooldows() -> None:
    async with async_session() as session:
        async with session.begin():
            stmt = (
                select(Cooldown)
                .filter(Cooldown.ends_at <= time.time())
                .order_by(Cooldown.ends_at)
            )
            for cooldown in (await session.execute(stmt)).scalars():
                try:
                    if cooldown.player_id == WORLD_ID:
                        await _process_world_cooldown(cooldown, session)
                    else:
                        await _process_player_cooldown(cooldown, session)
                except Exception as ex:
                    logging.exception(ex)


async def _process_world_cooldown(cooldown: Cooldown, session) -> None:
    if cooldown.id == StateEnum.BATTLE:
        await _process_world_battle(session)
        cooldown.ends_at = get_next_battle_timestamp(cooldown.ends_at)
    elif cooldown.id == StateEnum.DAY:
        await _process_world_cauldron(session)
        cooldown.ends_at = get_next_day_timestamp()
    elif cooldown.id == StateEnum.MONTH:
        await session.execute(delete(DiceRank))
        await session.execute(delete(BattleRank))
        cooldown.ends_at = get_next_month_timestamp()
    elif cooldown.id == StateEnum.YEAR:
        await session.execute(delete(CauldronRank))
        cooldown.ends_at = get_next_year_timestamp()
    else:
        logging.warning("Unknown world state: %s", cooldown.id)
        await session.delete(cooldown)


async def _process_world_cauldron(session) -> None:
    winner = ""
    stmt = (
        select(CauldronCoin)
        .order_by(func.random())
        .options(selectinload(CauldronCoin.player))
    )
    for coin in (await session.execute(stmt)).scalars():
        player = coin.player
        await session.delete(coin)
        await player.send_message(
            text=f"✨{winner or 'You'} received {CAULDRON_GIFT}💰 from the magic cauldron✨",
            file=None if winner else get_image("cauldron"),
        )
        if not winner:
            winner = player.get_name()
            player.gold += CAULDRON_GIFT
            cauldron_rank = await fetchone(
                session, select(CauldronRank).filter_by(id=player.id)
            )
            if cauldron_rank:
                cauldron_rank.gold += CAULDRON_GIFT
            else:
                player.cauldron_rank = CauldronRank(gold=CAULDRON_GIFT)


async def _process_world_battle(session) -> None:
    await session.execute(delete(BattleReport))  # clear old reports
    stmt = select(BattleTactic).options(
        selectinload(BattleTactic.player)
        .options(selectinload(Player.battle_rank))
        .options(selectinload(Player.cooldowns))
    )
    for battle_tactic in (await session.execute(stmt)).scalars():
        player = battle_tactic.player
        tactic = battle_tactic.tactic
        await session.delete(battle_tactic)
        victory = False
        monster_tactic = random.choice(list(CombatTactic))
        gold = random.randint((player.level + 1) // 2, player.level + 1)
        base_exp = random.randint((player.level + 1) // 2, player.level + 1)
        hit_points = player.max_hp // 3
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
                battle.hp = -player.reduce_hp(hit_points)  # -100% hit_points
        elif tactic == CombatTactic.FEINT:
            if monster_tactic == CombatTactic.HIT:
                battle.exp = max(base_exp // 4, 1)  # +25% Exp
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
                battle.hp = -player.reduce_hp(hit_points)  # -100% hit_points
            else:  # monster_tactic == CombatTactic.PARRY
                battle.exp = max(base_exp // 4, 1)  # +25% Exp

        if battle.exp and player.increase_exp(battle.exp):  # level up
            await player.notify_level_up()

        player.battle_report = battle
        if victory:
            if not player.battle_rank:
                player.battle_rank = BattleRank(victories=0)
            player.battle_rank.victories += 1


async def _process_player_cooldown(cooldown: Cooldown, session) -> None:
    stmt = (
        select(Player)
        .filter_by(id=cooldown.player_id)
        .options(selectinload(Player.thief))
        .options(selectinload(Player.cooldowns))
    )
    player = await fetchone(session, stmt)
    if cooldown.id == StateEnum.REST:
        if player.stamina < player.max_stamina:
            player.stamina += 1
        if player.stamina >= player.max_stamina:
            await session.delete(cooldown)
            await player.send_message(
                text="Stamina restored. You are ready for more adventures!"
            )
        else:
            cooldown.ends_at = cooldown.ends_at + STAMINA_COOLDOWN
    elif cooldown.id == StateEnum.HEALING:
        if player.hp < player.max_hp:
            player.hp += 1
        if player.hp >= player.max_hp:
            await session.delete(cooldown)
        else:
            cooldown.ends_at = cooldown.ends_at + LIFEREGEN_COOLDOWN
    elif cooldown.id == StateEnum.NOTICED_THIEF:
        thief = player.thief
        gold = calculate_thieve_gold(thief.level)
        thief.gold += gold
        exp = random.randint(1, 3)
        if thief.increase_exp(exp):  # level up
            await thief.notify_level_up()

        text = f"You let **{thief.get_name()}** rob the townsmen. We hope you feel terrible."
        await player.send_message(text=text)

        text = (
            f"**{player.get_name()}** was completely clueless. You successfully stole some loot."
            " You feel great.\n\n"
            f"💰Gold: {gold:+}\n"
            f"🔥Exp: {exp:+}\n"
        )
        await thief.send_message(text=text)
        player.stop_noticing()  # removes cooldown from session
    elif cooldown.id == StateEnum.PLAYING_DICE:
        await session.delete(cooldown)
        player.state = StateEnum.REST
        player.gold += DICE_FEE
        await player.send_message(text="No one sat down next to you =/")
    else:
        quest = get_quest(cooldown.id)
        if quest:
            await quest.end(player, session)
        else:
            logging.warning("Unknown quest: %s", cooldown.id)
        await session.delete(cooldown)
