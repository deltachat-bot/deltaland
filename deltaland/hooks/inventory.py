"""Inventory hooks"""
from deltabot_cli import AttrDict, events
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ..consts import EquipmentSlot
from ..orm import Item, Player, async_session, fetchone
from ..util import render_stats
from . import cli


@cli.on(events.NewMessage(command="/inv"))
async def inv_cmd(event: AttrDict) -> None:
    """Show inventory."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot,
            session,
            [selectinload(Player.items).selectinload(Item.base)],
        )
        if not player:
            return
        atk, max_atk, def_, max_def = await player.get_equipment_stats(session)

    equipment = []
    inventory = []
    for item in player.items:
        if item.slot == EquipmentSlot.BAG:
            inventory.append(item)
        else:
            equipment.append(item)
    items = ""
    if equipment:
        for item in equipment:
            items += f"{item} /off_{item.id:03}\n"
    text = f"**🎽Equipment {render_stats(atk, max_atk, def_, max_def) or '[-]'}**\n{items}\n"
    text += f"**🎒Bag: ({len(inventory)}/{player.inv_size}):**\n"
    if inventory:
        text += "\n".join(
            f"{item} /{'on' if item.base.equipable else 'use'}_{item.id:03}"
            for item in inventory
        )
    else:
        text += "[Empty]"
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/on"))
async def on_cmd(event: AttrDict) -> None:
    """Equip an item."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player or not await player.validate_resting(session):
                return

            stmt = (
                select(Item)
                .options(selectinload(Item.base))
                .filter_by(
                    id=int(event.payload), player_id=player.id, slot=EquipmentSlot.BAG
                )
            )
            item = await fetchone(session, stmt)
            if item:
                if item.required_level > player.level:
                    await player.send_message(
                        text="You need level {item.required_level} or higher to equip that item",
                        quoted_msg=event.message_snapshot.id,
                    )
                    return
                slot = item.get_slot()
                if slot == EquipmentSlot.BAG:
                    await player.send_message(
                        text="You can't equip that item",
                        quoted_msg=event.message_snapshot.id,
                    )
                    return
                stmt = select(Item).filter_by(player_id=player.id, slot=slot)
                if slot == EquipmentSlot.HANDS:
                    hand_items = (await session.execute(stmt)).scalars().all()
                    equipped_item = hand_items[1] if len(hand_items) == 2 else None
                else:
                    equipped_item = await fetchone(session, stmt)
                if equipped_item:
                    equipped_item.slot = EquipmentSlot.BAG
                item.slot = slot
                await player.send_message(
                    text=f"Item equipped: **{item}**\n\n{item.base.description}"
                )
            else:
                await player.send_message(
                    text="Item not found in your bag",
                    quoted_msg=event.message_snapshot.id,
                )


@cli.on(events.NewMessage(command="/off"))
async def off_cmd(event: AttrDict) -> None:
    """Unequip an item."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if (
                not player
                or not await player.validate_resting(session)
                or not await player.validate_inv(session)
            ):
                return

            stmt = (
                select(Item)
                .options(selectinload(Item.base))
                .filter(
                    Item.id == int(event.payload),
                    Item.player_id == player.id,
                    Item.slot != EquipmentSlot.BAG,
                )
            )
            item = await fetchone(session, stmt)
            if item:
                item.slot = EquipmentSlot.BAG
                await player.send_message(text=f"Item unequipped: **{item}**")
            else:
                await player.send_message(
                    text="You don't have that item equipped",
                    quoted_msg=event.message_snapshot.id,
                )
