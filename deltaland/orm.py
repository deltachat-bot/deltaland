"""database"""
# pylama:ignore=R0904,C0103
import asyncio
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Optional, Tuple

from deltabot_cli import AttrDict, Bot
from sqlalchemy import Column, ForeignKey, Integer, String, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.future import select
from sqlalchemy.orm import backref, relationship, sessionmaker
from sqlalchemy.sql.selectable import Select

from .consts import (
    LIFEREGEN_COOLDOWN,
    MAX_HP,
    MAX_LEVEL,
    MAX_STAMINA,
    STAMINA_COOLDOWN,
    STARTING_ATTACK,
    STARTING_DEFENSE,
    STARTING_GOLD,
    STARTING_INV_SIZE,
    STARTING_LEVEL,
    THIEVE_NOTICED_COOLDOWN,
    WORLD_ID,
    CombatTactic,
    EquipmentSlot,
    ItemType,
    StateEnum,
    Tier,
    equipable_items,
)
from .experience import required_exp
from .util import get_image, render_stats, send_message

if TYPE_CHECKING:
    from .quests import Quest

_session = None
_bot: Bot
_lock: asyncio.Lock


class Base:
    @declared_attr
    def __tablename__(cls):  # noqa
        return cls.__name__.lower()  # noqa


Base = declarative_base(cls=Base)  # noqa


class Game(Base):
    id = Column(Integer, primary_key=True)
    version = Column(Integer)

    def __init__(self, **kwargs):
        kwargs.setdefault("id", 0)
        super().__init__(**kwargs)


class Player(Base):
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    birthday = Column(Integer)
    level = Column(Integer)
    exp = Column(Integer)
    attack = Column(Integer)
    defense = Column(Integer)
    hp = Column(Integer)
    max_hp = Column(Integer)
    mana = Column(Integer)
    max_mana = Column(Integer)
    stamina = Column(Integer)
    max_stamina = Column(Integer)
    gold = Column(Integer)
    state = Column(Integer)
    thief_id = Column(Integer, ForeignKey("player.id"))
    inv_size = Column(Integer)
    last_seen = Column(Integer)
    thief = relationship(
        "Player",
        uselist=False,
        backref=backref("sentinel", uselist=False),
        remote_side="player.c.id",
    )
    cauldron_coin = relationship(
        "CauldronCoin",
        uselist=False,
        backref=backref("player", uselist=False),
        cascade="all, delete, delete-orphan",
    )
    battle_tactic = relationship(
        "BattleTactic",
        uselist=False,
        backref=backref("player", uselist=False),
        cascade="all, delete, delete-orphan",
    )
    battle_report = relationship(
        "BattleReport",
        uselist=False,
        backref=backref("player", uselist=False),
        cascade="all, delete, delete-orphan",
    )
    battle_rank = relationship(
        "BattleRank",
        uselist=False,
        backref=backref("player", uselist=False),
        cascade="all, delete, delete-orphan",
    )
    dice_rank = relationship(
        "DiceRank",
        uselist=False,
        backref=backref("player", uselist=False),
        cascade="all, delete, delete-orphan",
    )
    cauldron_rank = relationship(
        "CauldronRank",
        uselist=False,
        backref=backref("player", uselist=False),
        cascade="all, delete, delete-orphan",
    )
    sentinel_rank = relationship(
        "SentinelRank",
        uselist=False,
        backref=backref("player", uselist=False),
        cascade="all, delete, delete-orphan",
    )
    items = relationship("Item", backref="player", cascade="all, delete, delete-orphan")
    cooldowns = relationship(
        "Cooldown", backref="player", cascade="all, delete, delete-orphan"
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("level", STARTING_LEVEL)
        kwargs.setdefault("exp", 0)
        kwargs.setdefault("attack", STARTING_ATTACK)
        kwargs.setdefault("defense", STARTING_DEFENSE)
        kwargs.setdefault("hp", MAX_HP)
        kwargs.setdefault("max_hp", MAX_HP)
        kwargs.setdefault("stamina", MAX_STAMINA)
        kwargs.setdefault("max_stamina", MAX_STAMINA)
        kwargs.setdefault("gold", STARTING_GOLD)
        kwargs.setdefault("state", StateEnum.REST)
        kwargs.setdefault("inv_size", STARTING_INV_SIZE)
        kwargs.setdefault("birthday", int(time.time()))
        kwargs.setdefault("last_seen", kwargs["birthday"])
        super().__init__(**kwargs)

    async def send_message(self, **kwargs) -> None:
        await send_message(self.id, _bot.account, **kwargs)

    def get_name(self, show_id: bool = False) -> str:
        name = self.name or "Stranger"
        return f"{name} (🆔{self.id})" if show_id else name

    def increase_exp(self, exp: int) -> bool:
        """Return True if level increased, False otherwise"""
        if self.level == MAX_LEVEL:
            return False
        max_exp = required_exp(self.level + 1)
        self.exp += exp
        leveled_up = self.exp >= max_exp
        while self.exp >= max_exp:
            exp = self.exp - max_exp
            self.level += 1
            max_exp = required_exp(self.level + 1)
            self.exp = exp
        if leveled_up:
            index = -1
            for i, cooldwn in enumerate(self.cooldowns):
                if cooldwn.id == StateEnum.REST:
                    index = i
                    break
            if index >= 0:
                self.cooldowns.pop(index)
            if self.stamina < self.max_stamina:
                self.stamina = self.max_stamina
        return leveled_up

    def reduce_stamina(self, stamina: int) -> None:
        self.stamina -= stamina
        restoring = False
        for cooldwn in self.cooldowns:
            if cooldwn.id == StateEnum.REST:
                restoring = True
                break
        if self.stamina < self.max_stamina and not restoring:
            self.cooldowns.append(
                Cooldown(  # noqa
                    id=StateEnum.REST, ends_at=time.time() + STAMINA_COOLDOWN
                )
            )

    def reduce_hp(self, hit_points: int) -> int:
        """Returns the effective amount of hp reduced"""
        hit_points = min(self.hp - 1, hit_points)
        self.hp -= hit_points
        restoring = False
        for cooldwn in self.cooldowns:
            if cooldwn.id == StateEnum.HEALING:
                restoring = True
                break
        if self.hp < self.max_hp and not restoring:
            self.cooldowns.append(
                Cooldown(  # noqa
                    id=StateEnum.HEALING, ends_at=time.time() + LIFEREGEN_COOLDOWN
                )
            )
        return hit_points

    def start_quest(self, quest: "Quest") -> None:
        self.state = quest.id
        end = time.time() + quest.duration
        self.cooldowns.append(Cooldown(id=quest.id, ends_at=end))  # noqa
        self.reduce_stamina(quest.stamina_cost)

    def start_noticing(self, thief: "Player") -> None:
        self.state = StateEnum.NOTICED_THIEF
        thief.state = StateEnum.NOTICED_SENTINEL
        self.thief = thief
        self.cooldowns.append(
            Cooldown(  # noqa
                id=StateEnum.NOTICED_THIEF,
                ends_at=time.time() + THIEVE_NOTICED_COOLDOWN,
            )
        )

    def stop_noticing(self) -> None:
        thief = self.thief
        self.thief = None
        thief.state = self.state = StateEnum.REST
        index = -1
        for i, cooldwn in enumerate(self.cooldowns):
            if cooldwn.id == StateEnum.NOTICED_THIEF:
                index = i
                break
        assert index >= 0
        self.cooldowns.pop(index)

    @staticmethod
    def get_all() -> Select:
        return select(Player).filter(Player.id > 0)

    @staticmethod
    def get_all_active() -> Select:
        one_month_ago = int(time.time()) - 60 * 60 * 24 * 30
        return select(Player).filter(Player.id > 0, Player.last_seen > one_month_ago)

    @staticmethod
    def count() -> Select:
        return select(func.count()).select_from(Player).filter(Player.id > 0)

    @staticmethod
    async def from_message(
        msg: AttrDict, session: sessionmaker, options=None
    ) -> Optional["Player"]:
        """Get the player corresponding to a message.

        An error message is sent if the user have not joined the game yet
        """
        stmt = select(Player).filter_by(id=msg.sender.id)
        for option in options or []:
            stmt = stmt.options(option)
        player = await fetchone(session, stmt)
        if player:
            player.last_seen = int(time.time())
            return player
        text = (
            "You have not joined the game yet.\n\n"
            "Send /start to join the game\n"
            "Send /help for more info"
        )
        await send_message(msg.sender, text=text)
        return None

    async def validate_level(self, required_level: int) -> bool:
        if self.level >= required_level:
            return True
        await self.send_message(text="🍼 Your level is too low to perform that action.")
        return False

    async def validate_gold(self, required_gold: int) -> bool:
        if self.gold >= required_gold:
            return True
        await self.send_message(
            text="You don't even have enough gold for a pint of grog.\nWhy don't you get a job?"
        )
        return False

    async def used_inv_slots(self, session: sessionmaker) -> bool:
        stmt = (
            select(func.count())
            .select_from(Item)
            .filter_by(player_id=self.id, slot=EquipmentSlot.BAG)
        )
        return await fetchone(session, stmt)

    async def validate_inv(self, session: sessionmaker) -> bool:
        inv = await self.used_inv_slots(session)
        if inv < self.inv_size:
            return True
        await self.send_message(text="Your bag is full.")
        return False

    async def validate_stamina(self, required_stamina: int) -> bool:
        if self.stamina >= required_stamina:
            return True
        await self.send_message(
            text="Not enough stamina. Come back after you take a rest."
        )
        return False

    async def validate_hp(self) -> bool:
        if self.hp >= min(self.max_hp / 4, 100):
            return True
        await self.send_message(
            text="You need to heal your wounds and recover, come back later."
        )
        return False

    async def validate_resting(
        self,
        session: sessionmaker,
        ignore_battle: bool = False,
    ) -> bool:
        if not ignore_battle:
            stmt = select(Cooldown).filter_by(id=StateEnum.BATTLE, player_id=WORLD_ID)
            remaining_time = (await fetchone(session, stmt)).ends_at - time.time()
            if remaining_time <= 60 * 10:
                await self.send_message(
                    text="Goblin are about to attack. You have no time for games."
                )
                return False

        if self.state == StateEnum.REST:
            return True

        await self.send_message(
            text="You are too busy with a different adventure. Try a bit later."
        )
        return False

    async def get_equipment_stats(self, session: sessionmaker) -> Tuple[int, int]:
        stmt = select(Item).filter(
            Item.player_id == self.id, Item.slot != EquipmentSlot.BAG
        )
        atk, def_ = 0, 0
        for item in (await session.execute(stmt)).scalars():
            atk += item.attack or 0
            def_ += item.defense or 0
        return atk, def_

    async def notify_level_up(self) -> None:
        text = f"🎉 Congratulations! You reached level {self.level}!\n"
        if self.level == 2:
            text += (
                "The higher the level, the more activities become available to you.\n"
                "- Thieve quests are available at level 3.\n"
                "- World leaderboards are available at level 3."
            )
        elif self.level == 3:
            text += "- New quest Thieve unlocked!\n- You can learn how other players are doing via the leaderboards at /top"
            text += "\n\n**WARNING:** Work in progress, level 3 is the maximum level for now."
        await self.send_message(text=text, file=get_image("level-up"))

    def get_battle_report(self) -> str:
        battle = self.battle_report
        tie_msg = (
            "You both avoided each other's attacks."
            " The goblin was surprised by this outcome and ran away."
        )
        tie_damage_msg = (
            "You exchanged blows."
            " The wounded goblin fled as fast as he could, you fainted shortly after."
        )
        win_msg = "You killed the goblin. On his cold corpse you found some gold."
        lose_msg = "The blow was so strong that you fainted."
        hit_result = "{loser} feints but is defeated by {winner}'s hit!"
        feint_result = "{loser} tries to parry, but {winner} feints and hits!"
        parry_result = "{loser} tries to hit {winner}, but {winner} parries the attack and counterattacks!"
        monster_name = "the goblin"
        player_name = self.get_name()
        monster_tactic = battle.monster_tactic
        tactic = battle.tactic
        if tactic == CombatTactic.HIT:
            if monster_tactic == CombatTactic.HIT:
                text = tie_damage_msg
            elif monster_tactic == CombatTactic.FEINT:
                result = hit_result.format(winner=player_name, loser=monster_name)
                text = f"{result}\n{win_msg}"
            else:  # monster_tactic == CombatTactic.PARRY
                result = parry_result.format(winner=monster_name, loser=player_name)
                text = f"{result}\n{lose_msg}"
        elif tactic == CombatTactic.FEINT:
            if monster_tactic == CombatTactic.HIT:
                result = hit_result.format(winner=monster_name, loser=player_name)
                text = f"{result}\n{lose_msg}"
            elif monster_tactic == CombatTactic.FEINT:
                text = tie_damage_msg
            else:  # monster_tactic == CombatTactic.PARRY
                result = feint_result.format(winner=player_name, loser=monster_name)
                text = f"{result}\n{win_msg}"
        elif tactic == CombatTactic.PARRY:
            if monster_tactic == CombatTactic.HIT:
                result = parry_result.format(winner=player_name, loser=monster_name)
                text = f"{result}\n{win_msg}"
            elif monster_tactic == CombatTactic.FEINT:
                result = feint_result.format(winner=monster_name, loser=player_name)
                text = f"{result}\n{lose_msg}"
            else:  # monster_tactic == CombatTactic.PARRY
                text = tie_msg
        else:  # not parting on battle
            text = f"{player_name} was petrified by the fear and could't avoid {monster_name}'s attack.\n{lose_msg}"

        stats = "\n\n"
        if battle.exp:
            stats += f"🔥Exp: {battle.exp:+}\n"
        if battle.gold:
            stats += f"💰Gold: {battle.gold:+}\n"
        if battle.hp:
            stats += f"❤️HP: {battle.hp:+}\n"
        return (
            f"{player_name} 🏅{self.level}\n"
            "Your result on the battlefield:\n\n"
            "The goblins started to attack the castle,"
            f" one of them is quickly running towards {player_name}.\n\n"
            f"{text}{stats}"
        )


class BaseItem(Base):
    id = Column(Integer, primary_key=True)
    type = Column(Integer, nullable=False)
    tier = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(1000))
    attack = Column(Integer)
    defense = Column(Integer)
    items = relationship("Item", backref="base", cascade="all, delete, delete-orphan")

    @property
    def equipable(self) -> bool:
        return self.type in equipable_items

    def __init__(self, **kwargs):
        kwargs.setdefault("tier", Tier.NONE)
        super().__init__(**kwargs)

    def __str__(self) -> str:
        name = self.name
        stats = render_stats(self.attack, self.defense)
        if stats:
            name += f" {stats}"
        return name


class Item(Base):
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("player.id"))
    base_id = Column(Integer, ForeignKey("baseitem.id"))
    slot = Column(Integer, nullable=False)
    level = Column(Integer)
    attack = Column(Integer)
    defense = Column(Integer)
    base: BaseItem

    def __init__(self, **kwargs):
        kwargs.setdefault("slot", EquipmentSlot.BAG)
        super().__init__(**kwargs)

    @property
    def name(self) -> str:
        name = self.base.name
        if self.base.tier != Tier.NONE:
            name += f" lvl{self.level}"
        return name

    @property
    def required_level(self) -> int:
        return (self.base.tier or 0) * 10

    def __str__(self) -> str:
        name = self.name
        stats = render_stats(self.attack, self.defense)
        if stats:
            name += f" {stats}"
        return name

    def get_slot(self) -> EquipmentSlot:
        item_type = self.base.type
        if item_type in (ItemType.SWORD, ItemType.SHIELD):
            return EquipmentSlot.HANDS
        return EquipmentSlot.BAG


class Cooldown(Base):
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("player.id"), primary_key=True)
    ends_at = Column(Integer, nullable=False)


class BattleTactic(Base):
    id = Column(Integer, ForeignKey("player.id"), primary_key=True)
    tactic = Column(Integer, nullable=False)


class BattleReport(Base):
    id = Column(Integer, ForeignKey("player.id"), primary_key=True)
    tactic = Column(Integer, nullable=False)
    monster_tactic = Column(Integer, nullable=False)
    hp = Column(Integer, nullable=False)
    exp = Column(Integer, nullable=False)
    gold = Column(Integer, nullable=False)


class BattleRank(Base):
    id = Column(Integer, ForeignKey("player.id"), primary_key=True)
    victories = Column(Integer, nullable=False)


class DiceRank(Base):
    id = Column(Integer, ForeignKey("player.id"), primary_key=True)
    gold = Column(Integer, nullable=False)


class CauldronRank(Base):
    id = Column(Integer, ForeignKey("player.id"), primary_key=True)
    gold = Column(Integer, nullable=False)


class CauldronCoin(Base):
    id = Column(Integer, ForeignKey("player.id"), primary_key=True)


class SentinelRank(Base):
    id = Column(Integer, ForeignKey("player.id"), primary_key=True)
    stopped = Column(Integer, nullable=False)


@asynccontextmanager
async def async_session():
    """Get session"""
    async with _lock:
        async with _session() as session:
            yield session


async def init_db_engine(bot: Bot, path: str, debug: bool = False) -> None:
    """Initialize engine."""
    global _session, _bot, _lock  # noqa
    engine = create_async_engine(path, echo=debug)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # noqa

    _session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    _bot = bot
    _lock = asyncio.Lock()


async def fetchone(session: sessionmaker, stmt: Select) -> Any:
    return (await session.execute(stmt.limit(1))).scalars().first()
