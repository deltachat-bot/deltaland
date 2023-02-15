"""Constants"""
from enum import IntEnum

DATABASE_VERSION = 7
WORLD_ID = 0

MAX_LEVEL = 3
STARTING_LEVEL = 1
STARTING_ATTACK = 1
STARTING_DEFENSE = 1
STARTING_GOLD = 0
STARTING_INV_SIZE = 15
RANKS_REQ_LEVEL = 3
RESET_NAME_COST = 1000

CAULDRON_GIFT = 100

THIEVE_NOTICED_COOLDOWN = 60 * 3

MAX_STAMINA = 5
STAMINA_COOLDOWN = 60 * 60

MAX_HP = 40
LIFEREGEN_COOLDOWN = 30

DICE_FEE = 10
DICE_COOLDOWN = 60 * 5


class StateEnum(IntEnum):
    # Player state
    REST = 0
    PLAYING_DICE = -1
    HEALING = -2
    NOTICED_THIEF = -3
    NOTICED_SENTINEL = -4

    # World state
    DAY = -100
    MONTH = -101
    YEAR = -102
    BATTLE = -103


class CombatTactic(IntEnum):
    NONE = 0
    HIT = 1
    FEINT = 2
    PARRY = 3


class Quality(IntEnum):
    BAD = 0
    NORMAL = 1
    GOOD = 2


class EquipmentSlot(IntEnum):
    BAG = 0
    HANDS = 1
    HEAD = 2
    BODY = 3
    FEET = 4


class Tier(IntEnum):
    NONE = 0
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10


class ItemType(IntEnum):
    SWORD = 1
    SHIELD = 2


equipable_items = [ItemType.SWORD, ItemType.SHIELD]
