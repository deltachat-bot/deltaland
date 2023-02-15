"""Base items"""
from .consts import ItemType
from .orm import BaseItem


async def init_items(session) -> None:
    await session.merge(
        BaseItem(
            id=1,
            type=ItemType.SWORD,
            name="Wooden Sword",
            description="The type of wood used in this sword makes it light yet strong, although the same could be said for a broomstick...",
            attack=1,
            max_attack=5,
            shop_price=3,
        )
    )
    await session.merge(
        BaseItem(
            id=2,
            type=ItemType.SHIELD,
            name="Wooden Shield",
            description="A basic shield made of wood. To be honest, it looks a lot like the bottom of the barrels in the tavern.",
            defense=2,
            max_defense=3,
            shop_price=3,
        )
    )
