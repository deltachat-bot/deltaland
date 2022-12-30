"""hooks, filters and commands definitions."""
# pylama:ignore=W0603,C0103
import asyncio
import logging
import os
import random
import time
from argparse import Namespace

from simplebot_aio import AttrDict, Bot, BotCli, EventType, const, events
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from .consts import (
    DICE_FEE,
    RANKS_REQ_LEVEL,
    RESET_NAME_COST,
    CombatTactic,
    EquipmentSlot,
    StateEnum,
    Tier,
)
from .cooldown import cooldown_loop
from .dice import play_dice
from .experience import required_exp
from .game import get_next_battle_cooldown, get_next_day_cooldown, init_game
from .items import shop_items
from .migrations import run_migrations
from .orm import (
    BaseItem,
    BattleRank,
    BattleTactic,
    CauldronCoin,
    CauldronRank,
    Cooldown,
    DiceRank,
    Item,
    Player,
    SentinelRank,
    async_session,
    fetchone,
    init_db_engine,
)
from .quests import get_quest, quests
from .util import (
    calculate_interfere_gold,
    get_image,
    human_time_duration,
    is_valid_name,
    render_stats,
)

cli = BotCli("deltaland")
_hooks: dict


def is_not_known_command(event: AttrDict) -> bool:
    for hook in _hooks.get(events.NewMessage, []):
        cmd = hook[1].command
        if cmd and event.command == cmd:
            return False
    return True


@cli.on_init
async def on_init(bot: Bot, _args: Namespace) -> None:
    global _hooks
    _hooks = bot._hooks  # noqa
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
    asyncio.create_task(cooldown_loop())


@cli.on(events.RawEvent((EventType.INFO, EventType.WARNING, EventType.ERROR)))
async def log_event(event: AttrDict) -> None:
    getattr(logging, event.type.lower())(event.msg)


@cli.on(events.NewMessage(is_info=False, func=is_not_known_command))
async def filter_messages(event: AttrDict) -> None:
    """Deltaland bot.

    A game-bot that allows you to join the deltaland world and play with people all over the world.
    """
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
    """Start the game.

    Send this command to join the game.
    """
    msg = event.message_snapshot
    async with async_session() as session:
        async with session.begin():
            player = await fetchone(session, select(Player).filter_by(id=msg.sender.id))
            if player:
                already_joined = True
            else:
                already_joined = False
                player = Player(id=msg.sender.id, birthday=time.time())
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
            "3. Bug abusing without reporting them at https://github.com/adbenitez/deltaland",
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
        atk, def_ = await player.get_equipment_stats(session)
        await player.send_message(
            text=f"""Goblin attack in {battle_cooldown}!

            **{name}**{name_hint}
            🏅Level: {player.level}
            ⚔️Atk: {player.attack + atk}  🛡️Def: {player.defense + def_}
            🔥Exp: {player.exp}/{required_exp(player.level+1)}
            ❤️HP: {player.hp}/{player.max_hp}
            🔋Stamina: {player.stamina}/{player.max_stamina}{stamina_cooldown}
            💰{player.gold}

            🎽Equipment {render_stats(atk, def_) or "[-]"}
            🎒Bag: {used_inv_slots}/{player.inv_size} /inv

            State:
            {state}

            🗺️ Quests: /quests
            🏰 Castle: /castle
            ⚔️ Battle: /battle
            {rankings}
            """
        )


@cli.on(events.NewMessage(command="/battle"))
async def battle_cmd(event: AttrDict) -> None:
    """Choose battle tactics."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player and not await player.validate_resting(
                session, ignore_battle=True
            ):
                return

    text = (
        "Goblins are greedy creatures attracted by gold, they attack the castle every 8 hours.\n"
        "Select your combat plan for the next battle:\n\n"
        "**🗡️HIT**\nA precise hit avoiding feints, but can be parried.\n/hit\n\n"
        "**💥FEINT**\nA feint avoids the enemy's parry, but doesn't work against hits.\n/feint\n\n"
        "**⚔️PARRY**\nParry a hit and counterattack, but you could be deceived by a feint.\n/parry\n\n"
        "Last battle report: /report"
    )
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/hit"))
async def hit_cmd(event: AttrDict) -> None:
    """Choose HIT as battle tactic."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player and not await player.validate_resting(
                session, ignore_battle=True
            ):
                return
            player.battle_tactic = BattleTactic(tactic=CombatTactic.HIT)
            battle_cooldown = await get_next_battle_cooldown(session)
    text = (
        "So you will use **🗡️HIT** in the next battle, that sounds like a good plan."
        f" You joined the defensive formations. The next battle is in {battle_cooldown}."
    )
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/feint"))
async def feint_cmd(event: AttrDict) -> None:
    """Choose FEINT as battle tactic."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player and not await player.validate_resting(
                session, ignore_battle=True
            ):
                return
            player.battle_tactic = BattleTactic(tactic=CombatTactic.FEINT)
            battle_cooldown = await get_next_battle_cooldown(session)
    text = (
        "So you will use **💥FEINT** in the next battle, that sounds like a good plan."
        f" You joined the defensive formations. The next battle is in {battle_cooldown}."
    )
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/parry"))
async def parry_cmd(event: AttrDict) -> None:
    """Choose PARRY as battle tactic."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player and not await player.validate_resting(
                session, ignore_battle=True
            ):
                return
            player.battle_tactic = BattleTactic(tactic=CombatTactic.PARRY)
            battle_cooldown = await get_next_battle_cooldown(session)
    text = (
        "So you will use **⚔️PARRY** in the next battle, that sounds like a good plan."
        f" You joined the defensive formations. The next battle is in {battle_cooldown}."
    )
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/report"))
async def report_cmd(event: AttrDict) -> None:
    """Show your last results in the battlefield."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot, session, [selectinload(Player.battle_report)]
        )
        if not player:
            return

    if not player.battle_report:
        await player.send_message(text="You were not in the town in the last battle.")
    else:
        await player.send_message(
            text=player.get_battle_report(), file=get_image("goblin")
        )


@cli.on(events.NewMessage(command="/top"))
async def top_cmd(event: AttrDict) -> None:
    """Show the list of scoreboards."""
    async with async_session() as session:
        player = await Player.from_message(event.message_snapshot, session)
        if not player or not await player.validate_level(RANKS_REQ_LEVEL):
            return

    rankings = [
        "**📊 Ranking**",
        "**Goblin Slayers**\n⚔️ Most victories in the battlefield\n/top1",
        "**Midas's Disciples**\n💰 Top gold collectors\n/top2",
        "**Cauldron Worshipers**\n🍀 Most gold received from the magic cauldron\n/top3",
        "**Luckiest Gamblers**\n🎲 Most wins in dice\n/top4",
        "**Royal Guards**\n🗡️ Most thieves stopped\n/top5",
    ]
    await player.send_message(text="\n\n".join(rankings))


@cli.on(events.NewMessage(command="/top1"))
async def top1_cmd(event: AttrDict) -> None:
    """Most victories in the battlefield."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot, session, [selectinload(Player.battle_rank)]
        )
        if not player or not await player.validate_level(RANKS_REQ_LEVEL):
            return

        is_on_top = False
        text = ""
        stmt = (
            select(BattleRank)
            .options(selectinload(BattleRank.player))
            .order_by(BattleRank.victories.desc())
            .limit(15)
        )
        for i, rank in enumerate((await session.execute(stmt)).scalars()):
            if player.id == rank.id:
                is_on_top = True
                marker = "#️⃣"
            else:
                marker = "#"
            text += f"{marker}{i+1} {rank.player.get_name()} {rank.victories}⚔️\n"
    if not is_on_top and text:
        text += "\n...\n"
        victories = player.battle_rank.victories if player.battle_rank else 0
        text += f"{player.get_name()} {victories}⚔️"
    if text:
        text = "**⚔️ Most victories in the battlefield this month**\n\n" + text
    else:
        text = "Nobody has defeated goblins this month"
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/top2"))
async def top2_cmd(event: AttrDict) -> None:
    """Top gold collectors."""
    async with async_session() as session:
        player = await Player.from_message(event.message_snapshot, session)
        if not player or not await player.validate_level(RANKS_REQ_LEVEL):
            return

        is_on_top = False
        text = ""
        stmt = (
            Player.get_all()
            .filter(Player.gold > 0)
            .order_by(Player.gold.desc())
            .limit(15)
        )
        for i, player2 in enumerate((await session.execute(stmt)).scalars()):
            if player.id == player2.id:
                is_on_top = True
                marker = "#️⃣"
            else:
                marker = "#"
            text += f"{marker}{i+1} {player2.get_name()} {player2.gold}💰\n"
    if not is_on_top and text:
        text += "\n...\n"
        text += f"{player.get_name()} {player.gold}💰"
    if text:
        text = "**💰 Top gold collectors**\n\n" + text
    else:
        text = "Nobody has gold :("
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/top3"))
async def top3_cmd(event: AttrDict) -> None:
    """Most gold received from the magic cauldron."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot, session, [selectinload(Player.cauldron_rank)]
        )
        if not player or not await player.validate_level(RANKS_REQ_LEVEL):
            return

        is_on_top = False
        text = ""
        stmt = (
            select(CauldronRank)
            .options(selectinload(CauldronRank.player))
            .order_by(CauldronRank.gold.desc())
            .limit(15)
        )
        for i, rank in enumerate((await session.execute(stmt)).scalars()):
            if player.id == rank.id:
                is_on_top = True
                marker = "#️⃣"
            else:
                marker = "#"
            text += f"{marker}{i+1} {rank.player.get_name()} {rank.gold}💰\n"
    if not is_on_top and text:
        text += "\n...\n"
        gold = player.cauldron_rank.gold if player.cauldron_rank else 0
        text += f"{player.get_name()} {gold}💰"
    if text:
        text = "**🍀 Most gold received from the magic cauldron this year**\n\n" + text
    else:
        text = "Nobody has received gold from the magic cauldron this year"
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/top4"))
async def top4_cmd(event: AttrDict) -> None:
    """Most wins in dice this month."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot, session, [selectinload(Player.dice_rank)]
        )
        if not player or not await player.validate_level(RANKS_REQ_LEVEL):
            return

        is_on_top = False
        text = ""
        stmt = (
            select(DiceRank)
            .options(selectinload(DiceRank.player))
            .filter(DiceRank.gold > 0)
            .order_by(DiceRank.gold.desc())
            .limit(15)
        )
        for i, rank in enumerate((await session.execute(stmt)).scalars()):
            if player.id == rank.id:
                is_on_top = True
                marker = "#️⃣"
            else:
                marker = "#"
            text += f"{marker}{i+1} {rank.player.get_name()} {rank.gold}💰\n"
    if not is_on_top and text:
        text += "\n...\n"
        gold = player.dice_rank.gold if player.dice_rank else 0
        text += f"{player.get_name()} {gold}💰"
    if text:
        text = "**🎲 Most wins in dice this month**\n\n" + text
    else:
        text = "Nobody has earned gold playing dice this month"
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/top5"))
async def top5_cmd(event: AttrDict) -> None:
    """Most thieves stopped."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot, session, [selectinload(Player.sentinel_rank)]
        )
        if not player or not await player.validate_level(RANKS_REQ_LEVEL):
            return

        is_on_top = False
        text = ""
        stmt = (
            select(SentinelRank)
            .options(selectinload(SentinelRank.player))
            .order_by(SentinelRank.stopped.desc())
            .limit(15)
        )
        for i, rank in enumerate((await session.execute(stmt)).scalars()):
            if player.id == rank.id:
                is_on_top = True
                marker = "#️⃣"
            else:
                marker = "#"
            text += f"{marker}{i+1} {rank.player.get_name()} {rank.stopped}🗡️\n"
    if not is_on_top and text:
        text += "\n...\n"
        stopped = player.sentinel_rank.stopped if player.sentinel_rank else 0
        text += f"{player.get_name()} {stopped}🗡️"
    if text:
        text = "**🗡️ Most thieves stopped this month**\n\n" + text
    else:
        text = "Nobody has stopped thieves this month"
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/castle"))
async def castle_cmd(event: AttrDict) -> None:
    """Show options available inside the castle."""
    async with async_session() as session:
        player = await Player.from_message(event.message_snapshot, session)
        if not player or not await player.validate_resting(session):
            return
        player_count = await fetchone(session, Player.count())

    text = f"""**🏰 Gundor Castle**

    👥 Castle population: {player_count}
    🏚️ Shop: /shop
    🍺 Tavern: /tavern
    """
    await player.send_message(text=text, file=get_image("castle"))


@cli.on(events.NewMessage(command="/tavern"))
async def tavern_cmd(event: AttrDict) -> None:
    """Go to the tavern."""
    async with async_session() as session:
        player = await Player.from_message(event.message_snapshot, session)
        if not player or not await player.validate_resting(session):
            return

    text = f"""**🍺 Tavern**

    You walk inside The Lucky Cauldron Pub, loud and overcrowded as usual. Next to the bar you see some townsmen drinking grog and tossing coins in a cauldron with magic runes carved on it. In the back of the tavern some farmers are playing dice.

    You can toss a coin in the magic cauldron, once per day, the cauldron will reward with gold one of the adventurers who tossed a coin into it!
    Price: 1💰
    /cauldron

    Or you can sit next to the gamblers and try your luck in dice.
    Entry fee: {DICE_FEE}💰
    /dice
    """
    await player.send_message(text=text, file=get_image("tavern"))


@cli.on(events.NewMessage(command="/dice"))
async def dice_cmd(event: AttrDict) -> None:
    """Play dice in the tavern."""
    async with async_session() as session:
        async with session.begin():
            options = [selectinload(Player.dice_rank), selectinload(Player.cooldowns)]
            player = await Player.from_message(event.message_snapshot, session, options)
            if (
                not player
                or not await player.validate_resting(session)
                or not await player.validate_gold(DICE_FEE)
            ):
                return
            await play_dice(player, session)


@cli.on(events.NewMessage(command="/cauldron"))
async def cauldron_cmd(event: AttrDict) -> None:
    """Toss a coin in the magic cauldron."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(
                event.message_snapshot, session, [selectinload(Player.cauldron_coin)]
            )
            if not player or not await player.validate_resting(session):
                return

            cooldown = await get_next_day_cooldown(session)
            if player.cauldron_coin:
                await player.send_message(
                    text=f"You already tossed a coin, come again later. (⏰{cooldown})"
                )
            elif await player.validate_gold(1):
                player.gold -= 1
                player.cauldron_coin = CauldronCoin()
                await player.send_message(
                    text=f"You tossed a coin into the cauldron, it disappeared in the pitch black inside of the cauldron without making a sound.\n\n(⏰ Gift in {cooldown})"
                )


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


@cli.on(events.NewMessage(command="/inv"))
async def inv_cmd(event: AttrDict) -> None:
    """Show inventory."""
    async with async_session() as session:
        player = await Player.from_message(
            event.message_snapshot,
            session,
            [selectinload(Player.items).selectinload(Item.base)],
        )
        if not player:
            return

    equipment = []
    inventory = []
    for item in player.items:
        if item.slot == EquipmentSlot.BAG:
            inventory.append(item)
        else:
            equipment.append(item)
    items = ""
    atk, def_ = 0, 0
    if equipment:
        for item in equipment:
            items += f"{item} /off_{item.id:03}\n"
            atk += item.attack or 0
            def_ += item.defense or 0
    stats = render_stats(atk, def_) or "[-]"
    text = f"**🎽Equipment {stats}**\n{items}\n"
    text += f"**🎒Bag: ({len(inventory)}/{player.inv_size}):**\n"
    if inventory:
        text += "\n".join(
            f"{item} /{'on' if item.base.equipable else 'use'}_{item.id:03}"
            for item in inventory
        )
    else:
        text += "[Empty]"
    await player.send_message(text=text)


@cli.on(events.NewMessage(command="/shop"))
async def shop_cmd(event: AttrDict) -> None:
    """Go to the shop."""
    async with async_session() as session:
        player = await Player.from_message(event.message_snapshot, session)
        if not player or not await player.validate_resting(session):
            return

        text = "Welcome to our shop! We sell everything a person could ever need for adventuring.\n\n"
        text += f"**Reset Name Spell**\nPowerful spell to make everybody forget your name\n{RESET_NAME_COST}💰\n/buy_000\n\n"
        for item_id, price in sorted(shop_items.items()):
            base = await fetchone(session, select(BaseItem).filter_by(id=item_id))
            text += f"**{base}**\n{price}💰\n/buy_{base.id:03}\n\n"

    text += "\n---------\n💰To sell items: /sell"
    await player.send_message(text=text, file=get_image("shop"))


@cli.on(events.NewMessage(command="/buy"))
async def buy_cmd(event: AttrDict) -> None:
    """Buy an item."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if (
                not player
                or not await player.validate_resting(session)
                or not await player.validate_inv(session)
            ):
                return

            item_id = int(event.payload)
            if item_id == 0:
                if await player.validate_gold(RESET_NAME_COST):
                    player.gold -= RESET_NAME_COST
                    player.name = None
                    await player.send_message(
                        text="💫 Everyone forgot your name, you can set a new name with /name"
                    )
                return

            price = shop_items[item_id]
            if await player.validate_gold(price):
                base = await fetchone(session, select(BaseItem).filter_by(id=item_id))
                level = 1 if base.tier != Tier.NONE else None
                session.add(
                    Item(
                        player_id=player.id,
                        base_id=base.id,
                        level=level,
                        attack=base.attack,
                        defense=base.defense,
                    )
                )
                player.gold -= price
                await player.send_message(text="✅ Item added to your bag - /inv")


@cli.on(events.NewMessage(command="/sell"))
async def sell_cmd(event: AttrDict) -> None:
    """Sell an item in the shop."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player or not await player.validate_resting(session):
                return

            if event.payload:
                stmt = select(Item).filter_by(
                    id=int(event.payload), player_id=player.id, slot=EquipmentSlot.BAG
                )
                item = await fetchone(session, stmt)
                if item:
                    await session.delete(item)
                    player.gold += 1
                    await player.send_message(text="Item sold: +1💰")
                else:
                    await player.send_message(
                        text="Item not found in your bag",
                        quoted_msg=event.message_snapshot.id,
                    )
            else:
                stmt = (
                    select(Item)
                    .options(selectinload(Item.base))
                    .filter_by(player_id=player.id, slot=EquipmentSlot.BAG)
                )
                text = "Select item to sell:\n\n"
                for item in (await session.execute(stmt)).scalars():
                    text += f"**{item}**\n1💰 /sell_{item.id:03}\n\n"
                await player.send_message(text=text)


@cli.on(events.NewMessage(command="/on"))
async def on_cmd(event: AttrDict) -> None:
    """Equip an item."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if not player or not await player.validate_resting(session):
                return

            stmt = (
                select(Item)
                .options(selectinload(Item.base))
                .filter_by(
                    id=int(event.payload), player_id=player.id, slot=EquipmentSlot.BAG
                )
            )
            item = await fetchone(session, stmt)
            if item:
                if item.required_level > player.level:
                    await player.send_message(
                        text="You need level {item.required_level} or higher to equip that item",
                        quoted_msg=event.message_snapshot.id,
                    )
                    return
                slot = item.get_slot()
                if slot == EquipmentSlot.BAG:
                    await player.send_message(
                        text="You can't equip that item",
                        quoted_msg=event.message_snapshot.id,
                    )
                    return
                stmt = select(Item).filter_by(player_id=player.id, slot=slot)
                if slot == EquipmentSlot.HANDS:
                    hand_items = (await session.execute(stmt)).scalars().all()
                    equipped_item = hand_items[1] if len(hand_items) == 2 else None
                else:
                    equipped_item = await fetchone(session, stmt)
                if equipped_item:
                    equipped_item.slot = EquipmentSlot.BAG
                item.slot = slot
                await player.send_message(
                    text=f"Item equipped: **{item}**\n\n{item.base.description}"
                )
            else:
                await player.send_message(
                    text="Item not found in your bag",
                    quoted_msg=event.message_snapshot.id,
                )


@cli.on(events.NewMessage(command="/off"))
async def off_cmd(event: AttrDict) -> None:
    """Unequip an item."""
    async with async_session() as session:
        async with session.begin():
            player = await Player.from_message(event.message_snapshot, session)
            if (
                not player
                or not await player.validate_resting(session)
                or not await player.validate_inv(session)
            ):
                return

            stmt = (
                select(Item)
                .options(selectinload(Item.base))
                .filter(
                    Item.id == int(event.payload),
                    Item.player_id == player.id,
                    Item.slot != EquipmentSlot.BAG,
                )
            )
            item = await fetchone(session, stmt)
            if item:
                item.slot = EquipmentSlot.BAG
                await player.send_message(text=f"Item unequipped: **{item}**")
            else:
                await player.send_message(
                    text="You don't have that item equipped",
                    quoted_msg=event.message_snapshot.id,
                )
