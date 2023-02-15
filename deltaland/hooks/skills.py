"""Skills/Level-Up hooks"""
from deltabot_cli import AttrDict, events
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ..orm import BaseSkill, Player, Skill, async_session, fetchone

hooks = events.HookCollection()


@hooks.on(events.NewMessage(command="/level_up"))
async def levelup_cmd(event: AttrDict) -> None:
    """Improve skills."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot, session, [selectinload(Player.skills)]
        )
        if not player:
            return
        if player.skill_points:
            skills = list((await session.execute(select(BaseSkill))).scalars())

    if not player.skill_points:
        await player.send_message(
            text="You don't have any free skill point",
            quoted_msg=event.message_snapshot.id,
        )
        return

    player_skills = {}
    for skill in player.skills:
        player_skills[skill.id] = skill.level
    text = f"You have **{player.skill_points} sp.** What to improve?🤔\n\n"
    for skill in skills:
        level = player_skills.get(skill.id, 0) + 1
        text += (
            f"**{skill.name} lvl{level}** /learn_{skill.id:03}\n{skill.description}\n\n"
        )
    await player.send_message(text=text)


@hooks.on(events.NewMessage(command="/skills"))
async def skills_cmd(event: AttrDict) -> None:
    """See player skills."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot,
            session,
            [selectinload(Player.skills).selectinload(Skill.base)],
        )
        if not player:
            return

    text = ""
    for skill in player.skills:
        text += f"{skill.base.name} **lvl{skill.level}**\n"
    text = "**Learned Skills**\n\n" + (text or "🍼 You don't have any skill yet")
    await player.send_message(text=text)


@hooks.on(events.NewMessage(command="/learn"))
async def learn_cmd(event: AttrDict) -> None:
    """Level up an skill."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player or not await player.validate_sp(1):
                return

            skill_id = int(event.payload)
            stmt = (
                select(Skill)
                .filter_by(id=skill_id, player_id=player.id)
                .options(selectinload(Skill.base))
            )
            skill = await fetchone(session, stmt)
            if skill:
                base = skill.base
            else:
                base = await fetchone(session, select(BaseSkill).filter_by(id=skill_id))
                if not base:
                    await player.send_message(text="Invalid skill")
                    return
                skill = Skill(id=base.id, player_id=player.id, level=0)
                session.add(skill)

            player.skill_points -= 1
            skill.level += 1
            player.attack += base.min_atk
            player.max_attack += base.max_atk
            player.defense += base.min_def
            player.max_defense += base.max_def
            player.max_hp += base.max_hp
            player.hp += base.max_hp

    await player.send_message(text=f"✅ {base.name} have reached level {skill.level}")
