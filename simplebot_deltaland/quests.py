"""Game quests"""

import random
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .orm import Player


class Reward:
    def __init__(self, description: str, gold: int = 0, exp: int = 0) -> None:
        self.description = description
        self.gold = gold
        self.exp = exp


class Quest:
    def __init__(
        self,
        id: int,  # noqa
        name: str,
        description: str,
        status_msg: str,
        parting_msg: str,
        stamina: int,
        duration: int,
        rewards: List[Reward],
    ) -> None:
        self.id = id  # noqa
        self.name = name
        self.description = description
        self.status_msg = status_msg
        self.parting_msg = parting_msg
        self.stamina = stamina
        self.duration = duration
        self.rewards = rewards

    def get_reward(self, player: "Player") -> Reward:  # noqa
        return random.choice(self.rewards)


def get_quest(quest_id: int) -> Optional[Quest]:
    index = quest_id - 1
    return quests[index] if 0 <= index < len(quests) else None


quests = [
    Quest(
        id=1,
        name="Stroll the town",
        description="You decide to walk around in the town, looking for some easy errands that could get you a couple of coins",
        status_msg="👣 Strolling the town",
        parting_msg="You decided to stroll the town",
        stamina=1,
        duration=60 * 3,
        rewards=[
            Reward("You stepped on a pile of poop, you feel miserable"),
            Reward(
                "You was walking around when you noticed a gold coin on the floor!",
                gold=1,
            ),
            Reward(
                "You helped some kids to find their pet, they were a bit confused when you asked for your bounty",
                gold=1,
            ),
            Reward("You helped a farmer with the crops", gold=1),
            Reward(
                "In a dark alley you saw a thief threatening an old man, you helped him and shared the loot",
                gold=2,
            ),
            Reward(
                'You saw some rats in an alley, you killed them and sold their pelt as "rabbit pelt" to a local merchant',
                gold=2,
            ),
            Reward(
                "You helped the blacksmith with the chores, one of your fingers got hurt with a hammer",
                gold=2,
            ),
            Reward("You did some chores for a butcher", gold=2),
            Reward("You gave a hand in the Inn", gold=2),
            Reward("You helped a merchant with cargo", gold=2),
            Reward(
                "As you was walking in the crowded market you saw some gold coins falling from the pocket of a beautiful lady, you politely picked the coins and disappeared in the crowd",
                gold=3,
            ),
            Reward(
                "A man wearing elegant clothes, asked you to do some errands for him, he paid you well",
                gold=3,
            ),
        ],
    )
]
