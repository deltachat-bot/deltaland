"""Game quests"""
# pylama:ignore=C0103
import random
from dataclasses import dataclass
from typing import List, Optional

from simplebot_aio import AttrDict
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from .consts import Quality, StateEnum
from .orm import Player, async_session, fetchone
from .util import calculate_thieve_gold, human_time_duration


class QuestResult:
    def __init__(
        self, description: str, gold: int = 0, exp: int = 0, hp: int = 0
    ) -> None:
        self.description = description
        self.gold = gold
        self.exp = exp
        self.hp = hp


@dataclass
class Quest:
    id: int
    command_name: str
    name: str
    description: str
    status_msg: str
    parting_msg: str
    duration: int
    stamina_cost: int
    required_level: int

    async def command(self, event: AttrDict) -> None:
        """Command to start the quest"""
        async with async_session() as session:
            async with session.begin():
                player = await Player.from_message(
                    event.message_snapshot, session, [selectinload(Player.cooldowns)]
                )
                if (
                    not player
                    or not await player.validate_level(self.required_level)
                    or not await player.validate_resting(session)
                    or not await player.validate_hp()
                    or not await player.validate_stamina(self.stamina_cost)
                ):
                    return
                player.start_quest(self)

        duration = human_time_duration(self.duration, rounded=False)
        await player.send_message(
            text=f"{self.parting_msg}. You will be back in {duration}"
        )

    async def end(self, player: "Player", session) -> None:  # noqa
        """End the quest."""
        result = self.get_result(player)

        text = f"{result.description}\n\n"
        if result.exp:
            text += f"🔥Exp: {result.exp:+}\n"
            if player.increase_exp(result.exp):  # level up
                await player.notify_level_up()
        if result.gold:
            text += f"💰Gold: {result.gold:+}\n"
            player.gold += result.gold
        if result.hp:
            if result.hp < 0:
                result.hp = -player.reduce_hp(-result.hp)
            else:
                player.hp = min(player.hp + result.hp, player.max_hp)
            if result.hp:
                text += f"❤️HP: {result.hp:+}\n"

        player.state = StateEnum.REST
        await player.send_message(text=text)

    def get_result(self, player: "Player") -> QuestResult:  # noqa
        """End the quest."""
        return QuestResult(description="")


class ThieveQuest(Quest):
    def __init__(self) -> None:
        super().__init__(
            id=2,
            command_name="/thieve",
            name="🗡️Thieve",
            description="Thieving is a dangerous activity. Someone can notice you and beat you up. But if you go unnoticed, you will acquire a lot of loot.",
            status_msg="🗡️ Thieving in the town",
            parting_msg='This is not a fair world so you decide to take "what you deserve" with your own hands',
            stamina_cost=2,
            duration=60 * 2,
            required_level=3,
        )

    async def end(self, player: "Player", session) -> None:
        thief = player
        stmt = (
            Player.get_all()
            .options(selectinload(Player.cooldowns))
            .filter_by(state=StateEnum.REST)
            .order_by(func.random())
        )
        sentinel = await fetchone(session, stmt)
        if sentinel:
            await sentinel.send_message(
                text=f"You were wandering around when you noticed **{thief.get_name()}**"
                " trying to rob some townsmen.\n\n🛑 /interfere"
            )
            text = (
                f"Close to the place you are robbing you spotted warrior **{sentinel.get_name()}**."
                f" Let's hope **{sentinel.get_name()}** won't notice you."
            )
            await thief.send_message(text=text)
            sentinel.start_noticing(thief)
        else:
            thief.state = StateEnum.REST
            gold = calculate_thieve_gold(thief.level)
            thief.gold += gold
            exp = random.randint(1, 3)
            if thief.increase_exp(exp):  # level up
                await thief.notify_level_up()
            text = (
                "Nobody noticed you. You successfully stole some loot. You feel great.\n\n"
                f"💰Gold: {gold:+}\n"
                f"🔥Exp: {exp:+}\n"
            )
            await thief.send_message(text=text)


class TownQuest(Quest):
    def __init__(self) -> None:
        super().__init__(
            id=1,
            command_name="/wander",
            name="👣Wander around the town",
            description="You decide to wander around the town in the hope that something interesting will happen",
            status_msg="👣 Wandering around the town",
            parting_msg="You start to wander around the town",
            stamina_cost=1,
            duration=60 * 3,
            required_level=0,
        )

    def get_result(self, player: "Player") -> QuestResult:  # noqa
        quality = random.choices(
            (Quality.BAD, Quality.NORMAL, Quality.GOOD), weights=(10, 80, 10)
        )[0]
        if quality == Quality.NORMAL:
            return self.get_normal_result()
        if quality == Quality.GOOD:
            return self.get_good_result()
        return self.get_bad_result()

    def get_bad_result(self) -> QuestResult:
        descriptions = [
            "You helped a blacksmith with the chores. One of your fingers got hurt with a hammer",  # must be first item
            "You stepped on a pile of poop, lucky day :/",
            "You came back empty handed and bored",
            "A wagon passed near you and splashed water from a puddle, your clothes are wet and stinky",
            "You wandered around for a while but nothing interesting happened",
            'As you were strolling in the town you accidentally stepped on a puddle of dirty and stinky "water"',
        ]
        desc = random.choice(descriptions)
        if desc == descriptions[0]:  # hurt
            return QuestResult(
                description=desc,
                gold=random.randint(1, 2),
                exp=random.randint(1, 2),
                hp=-random.randint(5, 10),
            )
        return QuestResult(description=desc)

    def get_normal_result(self) -> QuestResult:
        descriptions = [
            "You were walking around when you noticed a gold coin on the floor!",  # must be first item
            "You helped some kids to find their pet, they were a bit confused when you asked for your bounty",
            "You helped a peasant with the crops. It was hard work but you feel pleased about helping people... and charging for it.",
            "A merchant asked for your help to transport some of his cargo to the main plaza, you helped him and received a reward",
            "In a dark alley you saw a thief threatening an old man, you helped him and shared the loot",
            'You saw some rats in an alley, you killed them and sold their pelt as "rabbit pelt" to a local merchant',
            "You ran some errands for a butcher, he paid you with a piece of bacon, you sold it to a fat guy for some gold",
            "You helped a peasant to fix his wagon loaded with fruit that had a broken wheel. He gave you some fruits, you sold them in the local market",
            "You helped a magician to gather some rats for his experiments",
            "As you were strolling you collided with a stranger who turned out to be a thief running from the guards, you received a reward for (accidentally) stopping the thief",
            "As you were strolling you came across a nobleman who asked you to run some errands",
            "In an alley someone tried to rob you, but you rob him instead",
            "You helped an artisan with his work",
            "An old retired knight asked you to run some errands",
            "A knight paid you to bathe and feed his horse",
            "You helped transporting weapons to the armory",
            "You worked as a helper in the inn's kitchen",
            "You found a job cleaning the royal stables",
            "As you wandered around, you saw a nobleman in a horse-drawn carriage, one of the carriage's wheels was broken. You helped repair the carriage and received some gold coins",
            "A peddler weighed down with basic supplies asked for your help to transport the supplies to the market",
        ]
        desc = random.choice(descriptions)
        if desc == descriptions[0]:  # one coin
            return QuestResult(description=desc, gold=1, exp=random.randint(1, 2))
        return QuestResult(
            description=desc,
            gold=random.randint(1, 2),
            exp=random.randint(1, 2),
        )

    def get_good_result(self) -> QuestResult:
        descriptions = [
            "You gave a hand cleaning the inn. They allowed you to take a snap in one of their comfortable beds",  # must be first item
            "As you were walking in the crowded market you saw some gold coins falling from the pocket of a beautiful lady, you politely picked the coins and disappeared in the crowd",
            'A man wearing elegant clothes asked you to deliver a golden small box to a distant village to someone called "Thaernd Orarani", you accepted the quest, after pretending to part away you sold the loot to a local merchant',
            'A magician asked for your assistance to organize his "library", a room full of old spell books laying all over the floor. After finishing, you politely refused to receive any payment and went away... to sell a grimoire you found in your pocket',
            "Wandering around you accidentally kicked an old pot near other trash, the pot broke and inside you found some gold coins! Later you came back the same way and saw a beggar screaming over the pieces of a broken pot, weird",
            "You came across a magician asking for help to brew a potion. You helped him to brew the potion, then he drunk it and became a talking frog, you sold the frog to a local pet shop",
        ]
        desc = random.choice(descriptions)
        if desc == descriptions[0]:  # heal
            return QuestResult(
                description=desc,
                gold=random.randint(2, 3),
                exp=random.randint(2, 3),
                hp=random.randint(5, 10),
            )
        return QuestResult(
            description=desc,
            gold=random.randint(3, 4),
            exp=random.randint(2, 3),
        )


def get_quest(quest_id: int) -> Optional[Quest]:
    index = quest_id - 1
    return quests[index] if 0 <= index < len(quests) else None


quests: List[Quest] = [TownQuest(), ThieveQuest()]
