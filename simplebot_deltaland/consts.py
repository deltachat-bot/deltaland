"""Constants"""
from enum import IntEnum

DATABASE_VERSION = 4
WORLD_ID = 0

MAX_LEVEL = 3
STARTING_LEVEL = 1
STARTING_ATTACK = 1
STARTING_DEFENSE = 1
STARTING_GOLD = 0
RANKS_REQ_LEVEL = 3

MIN_CAULDRON_GIFT = 20
MAX_CAULDRON_GIFT = 100

THIEVE_SPOTTED_COOLDOWN = 60 * 3

MAX_STAMINA = 5
STAMINA_COOLDOWN = 60 * 60

MAX_HP = 300
LIFEREGEN_COOLDOWN = 30

DICE_FEE = 10
DICE_COOLDOWN = 60 * 5


class StateEnum(IntEnum):
    # Player state
    REST = 0
    PLAYING_DICE = -1
    HEALING = -2
    SPOTTED_THIEF = -3

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
