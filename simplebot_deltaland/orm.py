"""database"""

from contextlib import contextmanager
from threading import Lock

from sqlalchemy import Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import backref, relationship, sessionmaker

from .consts import MAX_STAMINA, STARTING_GOLD, StateEnum


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
    cauldron_coin = Column(Integer)
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
        kwargs.setdefault("level", 1)
        kwargs.setdefault("exp", 0)
        kwargs.setdefault("stamina", MAX_STAMINA)
        kwargs.setdefault("max_stamina", MAX_STAMINA)
        kwargs.setdefault("gold", STARTING_GOLD)
        kwargs.setdefault("state", StateEnum.REST)
        kwargs.setdefault("cauldron_coin", 0)
        super().__init__(**kwargs)


class Cooldown(Base):
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("player.id"), primary_key=True)
    ends_at = Column(Integer, nullable=False)


class DiceRank(Base):
    id = Column(Integer, ForeignKey("player.id"), primary_key=True)
    gold = Column(Integer, nullable=False)


class CauldronRank(Base):
    id = Column(Integer, ForeignKey("player.id"), primary_key=True)
    gold = Column(Integer, nullable=False)


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
