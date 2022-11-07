"""Game quests"""

from typing import List, Optional


class Reward:
    def __init__(self, description: str, gold: int) -> None:
        self.description = description
        self.gold = gold


class Quest:
    def __init__(
        self,
        id: int,  # noqa
        name: str,
        description: str,
        stamina: int,
        duration: int,
        rewards: List[Reward],
    ) -> None:
        self.id = id  # noqa
        self.name = name
        self.description = description
        self.stamina = stamina
        self.duration = duration
        self.rewards = rewards


def get_quest(quest_id: int) -> Optional[Quest]:
    index = quest_id - 1
    return quests[index] if 0 <= index < len(quests) else None


quests = [
    Quest(
        1,
        "Stroll the town",
        "You decide to walk around in the town, looking for some easy errands that could get you a couple of coins",
        stamina=1,
        duration=60 * 5,
        rewards=[
            Reward(
                "You stepped on a pile of poop, you feel miserable",
                gold=0,
            ),
            Reward(
                "You was walking around when you noticed a gold coin on the floor!",
                gold=1,
            ),
            Reward(
                "You saw some rats, one of them had a gold coin, you killed them and took the gold",
                gold=1,
            ),
            Reward(
                "You helped some kids to find their pet, they were a bit confused when you asked for your bounty",
                gold=1,
            ),
            Reward(
                "In a dark alley you saw a thief threatening an old man, you helped him and shared the loot",
                gold=2,
            ),
            Reward(
                "You helped the blacksmith with the chores, one of your fingers got hurt with a hammer",
                gold=2,
            ),
            Reward("You helped a farmer with the crops", gold=2),
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
