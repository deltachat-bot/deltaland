"""Goblin Battle hooks"""
from deltabot_cli import AttrDict, events
from sqlalchemy.orm import selectinload

from ..game import get_next_battle_cooldown
from ..orm import BattleTactic, CombatTactic, Player, async_session
from ..util import get_image
from . import cli


@cli.on(events.NewMessage(command="/battle"))
async def battle_cmd(event: AttrDict) -> None:
    """Choose battle tactics."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player and not await player.validate_resting(
                session, ignore_battle=True
            ):
                return

    text = (
        "Goblins are greedy creatures attracted by gold, they attack the castle every 8 hours.\n"
        "Select your combat plan for the next battle:\n\n"
        "**🗡️HIT**\nA precise hit avoiding feints, but can be parried.\n/hit\n\n"
        "**💥FEINT**\nA feint avoids the enemy's parry, but doesn't work against hits.\n/feint\n\n"
        "**⚔️PARRY**\nParry a hit and counterattack, but you could be deceived by a feint.\n/parry\n\n"
        "Last battle report: /report"
    )
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/hit"))
async def hit_cmd(event: AttrDict) -> None:
    """Choose HIT as battle tactic."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player and not await player.validate_resting(
                session, ignore_battle=True
            ):
                return
            player.battle_tactic = BattleTactic(tactic=CombatTactic.HIT)
            battle_cooldown = await get_next_battle_cooldown(session)
    text = (
        "So you will use **🗡️HIT** in the next battle, that sounds like a good plan."
        f" You joined the defensive formations. The next battle is in {battle_cooldown}."
    )
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/feint"))
async def feint_cmd(event: AttrDict) -> None:
    """Choose FEINT as battle tactic."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player and not await player.validate_resting(
                session, ignore_battle=True
            ):
                return
            player.battle_tactic = BattleTactic(tactic=CombatTactic.FEINT)
            battle_cooldown = await get_next_battle_cooldown(session)
    text = (
        "So you will use **💥FEINT** in the next battle, that sounds like a good plan."
        f" You joined the defensive formations. The next battle is in {battle_cooldown}."
    )
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/parry"))
async def parry_cmd(event: AttrDict) -> None:
    """Choose PARRY as battle tactic."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player and not await player.validate_resting(
                session, ignore_battle=True
            ):
                return
            player.battle_tactic = BattleTactic(tactic=CombatTactic.PARRY)
            battle_cooldown = await get_next_battle_cooldown(session)
    text = (
        "So you will use **⚔️PARRY** in the next battle, that sounds like a good plan."
        f" You joined the defensive formations. The next battle is in {battle_cooldown}."
    )
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/report"))
async def report_cmd(event: AttrDict) -> None:
    """Show your last results in the battlefield."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot, session, [selectinload(Player.battle_report)]
        )
        if not player:
            return

    if not player.battle_report:
        await player.send_message(text="You didn't participate in the last battle.")
    else:
        await player.send_message(
            text=player.get_battle_report(), file=get_image("goblin")
        )
