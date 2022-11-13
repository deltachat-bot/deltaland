"""database"""

import time
from contextlib import contextmanager
from threading import Lock
from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import backref, relationship, sessionmaker

from .consts import (
    LIFEREGEN_COOLDOWN,
    MAX_HP,
    MAX_STAMINA,
    STAMINA_COOLDOWN,
    STARTING_ATTACK,
    STARTING_DEFENSE,
    STARTING_GOLD,
    STARTING_LEVEL,
    StateEnum,
)

if TYPE_CHECKING:
    from .quests import Quest


class Base:
    @declared_attr
    def __tablename__(cls):  # noqa
        return cls.__name__.lower()  # noqa


Base = declarative_base(cls=Base)  # noqa
_Session = sessionmaker()
_lock = Lock()


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
        super().__init__(**kwargs)

    def get_name(self, show_id: bool = False) -> str:
        name = self.name or "Stranger"
        return f"{name} (🆔{self.id})" if show_id else name

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
        self.cooldowns.append(
            Cooldown(id=quest.id, ends_at=time.time() + quest.duration)  # noqa
        )
        self.reduce_stamina(quest.stamina)


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


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    with _lock:
        session = _Session()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()


def init(path: str, debug: bool = False) -> None:
    """Initialize engine."""
    engine = create_engine(path, echo=debug)
    Base.metadata.create_all(engine)  # noqa
    _Session.configure(bind=engine)
