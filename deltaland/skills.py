"""Base skills"""
from .orm import BaseSkill


async def init_skills(session) -> None:
    await session.merge(
        BaseSkill(
            id=1,
            name="Brawler",
            description="Increase base attack +1⚔️ per level",
            min_atk=1,
            max_atk=1,
        )
    )
    await session.merge(
        BaseSkill(
            id=2,
            name="Sturdy Body",
            description="Increase base defense +2🛡️ per level",
            min_def=2,
            max_def=2,
        )
    )
    await session.merge(
        BaseSkill(
            id=3,
            name="Constitution",
            description="Increase life points +10❤️ per level",
            max_hp=10,
        )
    )
