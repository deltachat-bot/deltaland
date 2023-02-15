"""Rankings / leaderboards hooks"""
from deltabot_cli import AttrDict, events
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ..consts import RANKS_REQ_LEVEL
from ..orm import (
    BattleRank,
    CauldronRank,
    DiceRank,
    Player,
    SentinelRank,
    async_session,
)
from . import cli


@cli.on(events.NewMessage(command="/top"))
async def top_cmd(event: AttrDict) -> None:
    """Show the list of scoreboards."""
    async with async_session() as session:
        player = await Player.from_message(event.message_snapshot, session)
        if not player or not await player.validate_level(RANKS_REQ_LEVEL):
            return

    rankings = [
        "**📊 Ranking**",
        "**Goblin Slayers**\n⚔️ Most victories in the battlefield\n/top1",
        "**Midas's Disciples**\n💰 Top gold collectors\n/top2",
        "**Cauldron Worshipers**\n🍀 Most gold received from the magic cauldron\n/top3",
        "**Luckiest Gamblers**\n🎲 Most wins in dice\n/top4",
        "**Royal Guards**\n🗡️ Most thieves stopped\n/top5",
    ]
    await player.send_message(text="\n\n".join(rankings))


@cli.on(events.NewMessage(command="/top1"))
async def top1_cmd(event: AttrDict) -> None:
    """Most victories in the battlefield."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot, session, [selectinload(Player.battle_rank)]
        )
        if not player or not await player.validate_level(RANKS_REQ_LEVEL):
            return

        is_on_top = False
        text = ""
        stmt = (
            select(BattleRank)
            .options(selectinload(BattleRank.player))
            .order_by(BattleRank.victories.desc())
            .limit(15)
        )
        for i, rank in enumerate((await session.execute(stmt)).scalars()):
            if player.id == rank.id:
                is_on_top = True
                marker = "#️⃣"
            else:
                marker = "#"
            text += f"{marker}{i+1} {rank.player.get_name()} {rank.victories}⚔️\n"
    if not is_on_top and text:
        text += "\n...\n"
        victories = player.battle_rank.victories if player.battle_rank else 0
        text += f"{player.get_name()} {victories}⚔️"
    if text:
        text = "**⚔️ Most victories in the battlefield this month**\n\n" + text
    else:
        text = "Nobody has defeated goblins this month"
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/top2"))
async def top2_cmd(event: AttrDict) -> None:
    """Top gold collectors."""
    async with async_session() as session:
        player = await Player.from_message(event.message_snapshot, session)
        if not player or not await player.validate_level(RANKS_REQ_LEVEL):
            return

        is_on_top = False
        text = ""
        stmt = (
            Player.get_all()
            .filter(Player.gold > 0)
            .order_by(Player.gold.desc())
            .limit(15)
        )
        for i, player2 in enumerate((await session.execute(stmt)).scalars()):
            if player.id == player2.id:
                is_on_top = True
                marker = "#️⃣"
            else:
                marker = "#"
            text += f"{marker}{i+1} {player2.get_name()} {player2.gold}💰\n"
    if not is_on_top and text:
        text += "\n...\n"
        text += f"{player.get_name()} {player.gold}💰"
    if text:
        text = "**💰 Top gold collectors**\n\n" + text
    else:
        text = "Nobody has gold :("
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/top3"))
async def top3_cmd(event: AttrDict) -> None:
    """Most gold received from the magic cauldron."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot, session, [selectinload(Player.cauldron_rank)]
        )
        if not player or not await player.validate_level(RANKS_REQ_LEVEL):
            return

        is_on_top = False
        text = ""
        stmt = (
            select(CauldronRank)
            .options(selectinload(CauldronRank.player))
            .order_by(CauldronRank.gold.desc())
            .limit(15)
        )
        for i, rank in enumerate((await session.execute(stmt)).scalars()):
            if player.id == rank.id:
                is_on_top = True
                marker = "#️⃣"
            else:
                marker = "#"
            text += f"{marker}{i+1} {rank.player.get_name()} {rank.gold}💰\n"
    if not is_on_top and text:
        text += "\n...\n"
        gold = player.cauldron_rank.gold if player.cauldron_rank else 0
        text += f"{player.get_name()} {gold}💰"
    if text:
        text = "**🍀 Most gold received from the magic cauldron this year**\n\n" + text
    else:
        text = "Nobody has received gold from the magic cauldron this year"
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/top4"))
async def top4_cmd(event: AttrDict) -> None:
    """Most wins in dice this month."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot, session, [selectinload(Player.dice_rank)]
        )
        if not player or not await player.validate_level(RANKS_REQ_LEVEL):
            return

        is_on_top = False
        text = ""
        stmt = (
            select(DiceRank)
            .options(selectinload(DiceRank.player))
            .filter(DiceRank.gold > 0)
            .order_by(DiceRank.gold.desc())
            .limit(15)
        )
        for i, rank in enumerate((await session.execute(stmt)).scalars()):
            if player.id == rank.id:
                is_on_top = True
                marker = "#️⃣"
            else:
                marker = "#"
            text += f"{marker}{i+1} {rank.player.get_name()} {rank.gold}💰\n"
    if not is_on_top and text:
        text += "\n...\n"
        gold = player.dice_rank.gold if player.dice_rank else 0
        text += f"{player.get_name()} {gold}💰"
    if text:
        text = "**🎲 Most wins in dice this month**\n\n" + text
    else:
        text = "Nobody has earned gold playing dice this month"
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/top5"))
async def top5_cmd(event: AttrDict) -> None:
    """Most thieves stopped."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot, session, [selectinload(Player.sentinel_rank)]
        )
        if not player or not await player.validate_level(RANKS_REQ_LEVEL):
            return

        is_on_top = False
        text = ""
        stmt = (
            select(SentinelRank)
            .options(selectinload(SentinelRank.player))
            .order_by(SentinelRank.stopped.desc())
            .limit(15)
        )
        for i, rank in enumerate((await session.execute(stmt)).scalars()):
            if player.id == rank.id:
                is_on_top = True
                marker = "#️⃣"
            else:
                marker = "#"
            text += f"{marker}{i+1} {rank.player.get_name()} {rank.stopped}🗡️\n"
    if not is_on_top and text:
        text += "\n...\n"
        stopped = player.sentinel_rank.stopped if player.sentinel_rank else 0
        text += f"{player.get_name()} {stopped}🗡️"
    if text:
        text = "**🗡️ Most thieves stopped this month**\n\n" + text
    else:
        text = "Nobody has stopped thieves this month"
    await player.send_message(text=text)
