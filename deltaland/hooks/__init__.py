"""hooks, filters and commands definitions."""
# pylama:ignore=W0603,C0103
import logging
import os
import random
import time
from argparse import Namespace

from deltabot_cli import AttrDict, Bot, BotCli, EventType, const, events
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ..consts import RANKS_REQ_LEVEL, STARTING_LEVEL, EquipmentSlot, StateEnum, Tier
from ..cooldown import cooldown_loop
from ..experience import required_exp
from ..game import get_next_battle_cooldown, init_game
from ..migrations import run_migrations
from ..orm import (
    Cooldown,
    Item,
    Player,
    SentinelRank,
    async_session,
    fetchone,
    init_db_engine,
)
from ..quests import get_quest, quests
from ..util import (
    calculate_interfere_gold,
    get_image,
    human_time_duration,
    is_valid_name,
    render_stats,
    run_in_background,
)

cli = BotCli("deltaland")


@cli.on_init
async def on_init(bot: Bot, _args: Namespace) -> None:
    for quest in quests:
        bot.add_hook(quest.command, events.NewMessage(command=quest.command_name))

    if not await bot.account.get_config("displayname"):
        await bot.account.set_config("displayname", "Deltaland Bot")
        status = (
            "✨Deltaland, fantasy world, chat adventure, MMO game for Delta Chat,"
            " send me /help for more info"
        )
        await bot.account.set_config("selfstatus", status)
        await bot.account.set_config("selfavatar", get_image("castle"))


@cli.on_start
async def on_start(bot: Bot, args: Namespace) -> None:
    path = os.path.join(args.config_dir, "game.db")
    run_migrations(path)
    await init_db_engine(bot, f"sqlite+aiosqlite:///{path}")
    await init_game()
    logging.info("Listening for messages at: %s", await bot.account.get_config("addr"))
    run_in_background(cooldown_loop())


@cli.on(events.RawEvent((EventType.INFO, EventType.WARNING, EventType.ERROR)))
async def log_event(event: AttrDict) -> None:
    getattr(logging, event.type.lower())(event.msg)


@cli.on(events.NewMessage(is_info=False, func=cli.is_not_known_command))
async def filter_messages(event: AttrDict) -> None:
    """Fallback to /me if the message was not understood."""
    chat = await event.message_snapshot.chat.get_basic_snapshot()
    if chat.chat_type == const.ChatType.SINGLE:
        await me_cmd(event)


@cli.on(events.NewMessage(command="/help"))
async def help_cmd(event: AttrDict) -> None:
    lines = [
        "**Deltaland Bot**",
        "Hello wanderer, I am a game-bot that allows to join the Deltaland world and play"
        " a MMO chat-game full of fun and adventure with people all over the world!\n",
        "/help - show this help message.\n",
        "/start - send this command to join the game.\n",
        "/name - set your in-game name.\n",
    ]
    await event.message_snapshot.chat.send_message(text="\n".join(lines))


@cli.on(events.NewMessage(command="/start"))
async def start_cmd(event: AttrDict) -> None:
    """Start the game."""
    msg = event.message_snapshot
    async with async_session() as session:
        async with session.begin():
            player = await fetchone(session, select(Player).filter_by(id=msg.sender.id))
            if player:
                already_joined = True
            else:
                already_joined = False
                player = Player(id=msg.sender.id)
                if event.payload == "confirm":
                    session.add(player)

    if already_joined:
        await player.send_message(text="❌ You already joined the game")
    elif event.payload == "confirm":
        lines = [
            "Welcome to Deltaland, a fantasy world full of adventures and fun!\n",
            "You have just arrived to the **Gundor Castle**. It is a lively community"
            " surrounded by lush forest and rolling hills.\n",
            "To set your in-game name, type in /name followed by your name, for example:",
            "/name Thenali Ldulir\n",
            "To see your status send: /me",
        ]
        await player.send_message(text="\n".join(lines), file=get_image("splash"))
    else:
        lines = [
            "**⚠️Terms & Conditions**\n",
            "🛑 Forbidden:",
            "1. Scripts, automating, bots",
            "2. Multiple accounts",
            "3. Bug abusing without reporting them at https://github.com/deltachat-bot/deltaland",
            "4. Character and other in-game values trading",
            "5. Personal insults\n",
            "The game is provided AS IS. If you don't like it - you can simply not play it.",
            "Main principles - fair play. Don't cheat and don't try to find a hole in the rules.\n",
            "For breaking the rules, different sanctions may apply, up to permament in-game ban.",
            "Administration has the right to refuse access to the game to any player.\n",
            "Accept Terms: /start_confirm",
        ]
        await player.send_message(text="\n".join(lines))


@cli.on(events.NewMessage(command="/name"))
async def name_cmd(event: AttrDict) -> None:
    """Set your name."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player or not await player.validate_resting(session):
                return

            if player.name:
                await player.send_message(
                    text="❌ You already set a name. Perhaps in the /shop someone can help you to forget your current name"
                )
            else:
                payload = " ".join(event.payload.split())
                if is_valid_name(payload):
                    player.name = payload
                    await player.send_message(text=f"You set your name to: {payload}")
                else:
                    await player.send_message(
                        text="❌ Invalid name, the name can only have numbers and letters, and can be up to 16 characters long"
                    )


@cli.on(events.NewMessage(command="/me"))
async def me_cmd(event: AttrDict) -> None:
    """Show your status."""
    async with async_session() as session:
        options = [
            selectinload(Player.battle_tactic),
            selectinload(Player.sentinel),
            selectinload(Player.thief),
        ]
        player = await Player.from_message(event.message_snapshot, session, options)
        if not player:
            return

        now = time.time()
        name = player.get_name()
        name_hint = " (set name with /name)" if not player.name else ""
        if player.state == StateEnum.REST:
            if player.battle_tactic:
                state = "🏰 Defending the castle"
            else:
                state = "🛌 Resting"
        elif player.state == StateEnum.PLAYING_DICE:
            state = "🎲 Rolling the dice"
        elif player.state == StateEnum.NOTICED_THIEF:
            state = "👀 noticed **{player.thief.get_name()}** stealing"
        elif player.state == StateEnum.NOTICED_SENTINEL:
            state = f"👀 hiding from **{player.sentinel.get_name()}**"
        else:
            quest = get_quest(player.state)
            if quest:
                stmt = select(Cooldown).filter_by(id=quest.id, player_id=player.id)
                cooldown = await fetchone(session, stmt)
                quest_cooldown = human_time_duration(cooldown.ends_at - now)
                state = f"{quest.status_msg}. Back in {quest_cooldown}"
            else:
                state = f"UNKNOWN ({player.state})"
        stmt = select(Cooldown).filter_by(id=StateEnum.REST, player_id=player.id)
        cooldown = await fetchone(session, stmt)
        if cooldown:
            stamina_cooldown = " ⏰"
            seconds = cooldown.ends_at - now
            if seconds < 60:
                stamina_cooldown += "now"
            else:
                stamina_cooldown += human_time_duration(seconds)
        else:
            stamina_cooldown = ""
        battle_cooldown = await get_next_battle_cooldown(session)

        used_inv_slots = await player.used_inv_slots(session)

        rankings = "📊 Ranking: /top" if player.level >= RANKS_REQ_LEVEL else ""
        level_up = (
            "⭐Skill Points Available⭐\nPress /level_up\n\n"
            if player.skill_points > 0
            else ""
        )
        skills = "⭐ Skills: /skills" if player.level > STARTING_LEVEL else ""
        atk, max_atk, def_, max_def = await player.get_equipment_stats(session)
        lines = [
            f"{level_up}Goblin attack in {battle_cooldown}!",
            "",
            f"**{name}**{name_hint}",
            f"🏅Level: {player.level}",
            f"⚔️Atk: {player.attack + atk}-{player.max_attack + max_atk}"
            f"  🛡️Def: {player.defense + def_}-{player.max_defense + max_def}",
            f"🔥Exp: {player.exp}/{required_exp(player.level+1)}",
            f"❤️HP: {player.hp}/{player.max_hp}",
            f"🔋Stamina: {player.stamina}/{player.max_stamina}{stamina_cooldown}",
            f"💰{player.gold}",
            "",
            f"🎽Equipment {render_stats(atk, max_atk, def_, max_def) or '[-]'}",
            f"🎒Bag: {used_inv_slots}/{player.inv_size} /inv",
            "",
            "State:",
            f"{state}",
            "",
            f"{skills}",
            "🗺️ Quests: /quests",
            "🏰 Castle: /castle",
            "⚔️ Battle: /battle",
            f"{rankings}",
        ]
        await player.send_message(text="\n".join(lines))


@cli.on(events.NewMessage(command="/castle"))
async def castle_cmd(event: AttrDict) -> None:
    """Show options available inside the castle."""
    async with async_session() as session:
        player = await Player.from_message(event.message_snapshot, session)
        if not player or not await player.validate_resting(session):
            return
        player_count = await fetchone(session, Player.count())

    lines = [
        "**🏰 Gundor Castle**",
        "",
        f"👥 Castle population: {player_count}",
        "🏚️ Shop: /shop",
        "🍺 Tavern: /tavern",
    ]
    await player.send_message(text="\n".join(lines), file=get_image("castle"))


@cli.on(events.NewMessage(command="/quests"))
async def quests_cmd(event: AttrDict) -> None:
    """Show available quests."""
    async with async_session() as session:
        player = await Player.from_message(event.message_snapshot, session)
        if not player:
            return

    text = ""
    for quest in quests:
        if quest.required_level > player.level:
            continue
        duration = human_time_duration(quest.duration, rounded=False)
        text += (
            f"**{quest.name}** (⏰{duration}, 🔋{quest.stamina_cost})\n"
            f"{quest.description}\n{quest.command_name}\n\n"
        )
    if not text:
        text = "No available quests at the moment."
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/interfere"))
async def interfere_cmd(event: AttrDict) -> None:
    """Stop a thief."""
    async with async_session() as session:
        async with session.begin():
            options = [
                selectinload(Player.thief).selectinload(Player.cooldowns),
                selectinload(Player.cooldowns),
                selectinload(Player.sentinel_rank),
            ]
            player = await Player.from_message(event.message_snapshot, session, options)
            if not player:
                return

            if player.thief:
                thief: Player = player.thief

                player.stop_noticing()
                if not player.sentinel_rank:
                    player.sentinel_rank = SentinelRank(stopped=0)
                player.sentinel_rank.stopped += 1
                player_gold = random.randint(1, 2)
                player.gold += player_gold
                player_exp = random.randint(1, 3)
                if player.increase_exp(player_exp):  # level up
                    await player.notify_level_up()
                text = (
                    "You called the town's guards and charged at the thief."
                    f" **{thief.get_name()}** fled but not before receiving one of your blows."
                    " The townsmen gave you some gold coins as reward.\n\n"
                    f"💰Gold: {player_gold:+}\n"
                    f"🔥Exp: {player_exp:+}\n"
                )
                await player.send_message(text=text)

                thief_gold = -min(calculate_interfere_gold(thief.level), thief.gold)
                thief.gold += thief_gold
                lost_hp = -thief.reduce_hp(random.randint(50, 80))
                text = (
                    f"**{player.get_name()}** noticed you and called the town's guards."
                    " You tried to flee but received some hits before managing to escape."
                )
                if thief_gold:
                    text += " While running you accidentally lost some gold coins.\n\n"
                else:
                    text += "\n\n"
                if thief_gold:
                    text += f"💰Gold: {thief_gold:+}\n"
                text += f"❤️HP: {lost_hp:+}\n"
                await thief.send_message(text=text)
            else:
                await player.send_message(text="Too late. Action is not available")
