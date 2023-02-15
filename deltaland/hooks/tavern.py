"""Tavern hooks"""
from deltabot_cli import AttrDict, events
from sqlalchemy.orm import selectinload

from ..consts import DICE_FEE
from ..dice import play_dice
from ..game import get_next_day_cooldown
from ..orm import CauldronCoin, Player, async_session
from ..util import get_image
from . import cli


@cli.on(events.NewMessage(command="/tavern"))
async def tavern_cmd(event: AttrDict) -> None:
    """Go to the tavern."""
    async with async_session() as session:
        player = await Player.from_message(event.message_snapshot, session)
        if not player or not await player.validate_resting(session):
            return

    lines = [
        "**🍺 Tavern**",
        "",
        "You walk inside The Lucky Cauldron Pub, loud and overcrowded as usual. Next to the bar you"
        " see some townsmen drinking grog and tossing coins in a cauldron with magic runes carved on"
        " it. In the back of the tavern some farmers are playing dice.",
        "",
        "You can toss a coin in the magic cauldron, once per day, the cauldron will reward with"
        " gold one of the adventurers who tossed a coin into it!",
        "Price: 1💰",
        "/cauldron",
        "",
        "Or you can sit next to the gamblers and try your luck in dice.",
        "Entry fee: {DICE_FEE}💰",
        "/dice",
    ]
    await player.send_message(text="\n".join(lines), file=get_image("tavern"))


@cli.on(events.NewMessage(command="/dice"))
async def dice_cmd(event: AttrDict) -> None:
    """Play dice in the tavern."""
    async with async_session() as session:
        async with session.begin():
            options = [selectinload(Player.dice_rank), selectinload(Player.cooldowns)]
            player = await Player.from_message(event.message_snapshot, session, options)
            if (
                not player
                or not await player.validate_resting(session)
                or not await player.validate_gold(DICE_FEE)
            ):
                return
            await play_dice(player, session)


@cli.on(events.NewMessage(command="/cauldron"))
async def cauldron_cmd(event: AttrDict) -> None:
    """Toss a coin in the magic cauldron."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(
                event.message_snapshot, session, [selectinload(Player.cauldron_coin)]
            )
            if not player or not await player.validate_resting(session):
                return

            cooldown = await get_next_day_cooldown(session)
            if player.cauldron_coin:
                await player.send_message(
                    text=f"You already tossed a coin, come again later. (⏰{cooldown})"
                )
            elif await player.validate_gold(1):
                player.gold -= 1
                player.cauldron_coin = CauldronCoin()
                text = (
                    "You tossed a coin into the cauldron, it disappeared in the pitch black"
                    f" inside of the cauldron without making a sound.\n\n(⏰ Gift in {cooldown})"
                )
                await player.send_message(text=text)
