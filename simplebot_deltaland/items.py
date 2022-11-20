"""Base items"""
from .consts import ItemType
from .orm import BaseItem

shop_items = {1: 3, 2: 3}


def init_items(session) -> None:
    session.merge(
        BaseItem(
            id=1,
            type=ItemType.SWORD,
            name="Wooden Sword",
            description="The type of wood used in this sword makes it light yet strong, although the same could be said for a broomstick...",
            attack=1,
        )
    )
    session.merge(
        BaseItem(
            id=2,
            type=ItemType.SHIELD,
            name="Wooden Shield",
            description="A basic shield made of wood. To be honest, it looks a lot like the bottom of the barrels in the tavern.",
            defense=1,
        )
    )
