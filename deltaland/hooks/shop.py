"""Shop hooks"""
from deltabot_cli import AttrDict, events
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ..consts import RESET_NAME_COST, EquipmentSlot, Tier
from ..orm import BaseItem, Item, Player, async_session, fetchone
from ..util import get_image
from . import cli


@cli.on(events.NewMessage(command="/shop"))
async def shop_cmd(event: AttrDict) -> None:
    """Go to the shop."""
    async with async_session() as session:
        player = await Player.from_message(event.message_snapshot, session)
        if not player or not await player.validate_resting(session):
            return
        stmt = select(BaseItem).filter(BaseItem.shop_price > 0)
        base_items = (await session.execute(stmt)).scalars()

    text = (
        "Welcome to our shop! We sell everything a person could ever need for adventuring.\n\n"
        "**Reset Name Spell**\nPowerful spell to make everybody forget your name\n"
        f"{RESET_NAME_COST}💰\n/buy_000\n\n"
    )
    for base in base_items:
        text += f"**{base}**\n{base.shop_price}💰\n/buy_{base.id:03}\n\n"
    text += "\n---------\n💰To sell items: /sell"
    await player.send_message(text=text, file=get_image("shop"))


@cli.on(events.NewMessage(command="/buy"))
async def buy_cmd(event: AttrDict) -> None:
    """Buy an item."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if (
                not player
                or not await player.validate_resting(session)
                or not await player.validate_inv(session)
            ):
                return

            item_id = int(event.payload)
            if item_id == 0:
                if await player.validate_gold(RESET_NAME_COST):
                    player.gold -= RESET_NAME_COST
                    player.name = None
                    await player.send_message(
                        text="💫 Everyone forgot your name, you can set a new name with /name"
                    )
                return

            base = await fetchone(session, select(BaseItem).filter_by(id=item_id))
            if await player.validate_gold(base.shop_price):
                level = 1 if base.tier != Tier.NONE else None
                session.add(
                    Item(
                        player_id=player.id,
                        base_id=base.id,
                        level=level,
                        attack=base.attack,
                        max_attack=base.max_attack,
                        defense=base.defense,
                        max_defense=base.max_defense,
                    )
                )
                player.gold -= base.shop_price
                await player.send_message(text="✅ Item added to your bag - /inv")


@cli.on(events.NewMessage(command="/sell"))
async def sell_cmd(event: AttrDict) -> None:
    """Sell an item in the shop."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player or not await player.validate_resting(session):
                return

            if event.payload:
                stmt = select(Item).filter_by(
                    id=int(event.payload), player_id=player.id, slot=EquipmentSlot.BAG
                )
                item = await fetchone(session, stmt)
                if item:
                    await session.delete(item)
                    player.gold += 1
                    await player.send_message(text="Item sold: +1💰")
                else:
                    await player.send_message(
                        text="Item not found in your bag",
                        quoted_msg=event.message_snapshot.id,
                    )
            else:
                stmt = (
                    select(Item)
                    .options(selectinload(Item.base))
                    .filter_by(player_id=player.id, slot=EquipmentSlot.BAG)
                )
                text = "Select item to sell:\n\n"
                for item in (await session.execute(stmt)).scalars():
                    text += f"**{item}**\n1💰 /sell_{item.id:03}\n\n"
                await player.send_message(text=text)
