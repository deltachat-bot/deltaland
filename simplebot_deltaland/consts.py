"""Constants"""

from enum import IntEnum

WORLD_ID = 0
MAX_STAMINA = 5
STARTING_GOLD = 0
DICE_FEE = 10
MIN_CAULDRON_GIFT = 20
MAX_CAULDRON_GIFT = 100

STAMINA_COOLDOWN = 60 * 60
DICE_COOLDOWN = 60 * 5


class StateEnum(IntEnum):
    # Player state
    REST = 0
    PLAYING_DICE = -1

    # World state
    DAY = -100
    MONTH = -101
    YEAR = -102
