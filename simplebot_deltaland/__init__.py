"""hooks, filters and commands definitions."""

import os
import time
from threading import Thread

import simplebot
from deltachat import Message
from simplebot import DeltaBot
from simplebot.bot import Replies

from .consts import DICE_FEE, STAMINA_COOLDOWN, StateEnum
from .cooldown import cooldown_loop
from .dice import play_dice
from .game import get_next_day_cooldown, init_game
from .orm import CauldronRank, Cooldown, DiceRank, Player, init, session_scope
from .quests import get_quest, quests
from .util import (
    get_image,
    get_name,
    get_player,
    get_players,
    human_time_duration,
    is_valid_name,
    setdefault,
    validate_gold,
    validate_resting,
)


@simplebot.hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    setdefault(bot, "max_players", "0")


@simplebot.hookimpl
def deltabot_start(bot: DeltaBot) -> None:
    path = os.path.join(os.path.dirname(bot.account.db_path), __name__)
    if not os.path.exists(path):
        os.makedirs(path)
    path = os.path.join(path, "sqlite.db")
    init(f"sqlite:///{path}")
    init_game()
    Thread(target=cooldown_loop, args=(bot,), daemon=True).start()


@simplebot.filter
def filter_messages(message: Message, replies: Replies) -> None:
    """Deltaland bot.

    A game-bot that allows you to join the deltaland world and play with people all over the world.
    """
    if not message.chat.is_multiuser():
        me_cmd(message, replies)


@simplebot.command
def start(bot: DeltaBot, message: Message, replies: Replies) -> None:
    """Start the game.

    Send this command to join the game.
    """
    player_id = message.get_sender_contact().id
    with session_scope() as session:
        if session.query(Player).filter_by(id=player_id).first():
            replies.add(text="❌ You already joined the game")
            return
        max_players = int(setdefault(bot, "max_players"))
        if 0 < max_players <= get_players(session).count():
            replies.add(
                text="❌ This is unfortunate, but the game is not accepting new players at the moment"
            )
            return
        session.add(Player(id=player_id, birthday=time.time()))
    lines = [
        "Welcome to Deltaland, a fantasy world full of adventures and fun!",
        "",
        "You have just arrived to the castle town. It is a small but lively community surrounded by lush forest and rolling hills.",
        "",
        "To set your name in the game, type in /name followed by your name, for example:",
        "/name John",
        "",
        "To see your status send: /me",
    ]
    replies.add(text="\n".join(lines), filename=get_image("castle"))


@simplebot.command(name="/name", hidden=True)
def name_cmd(payload: str, message: Message, replies: Replies) -> None:
    """Set your name."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player or not validate_resting(player, replies):
            return

        if player.name:
            replies.add(text="❌ You already set a name")
        else:
            payload = " ".join(payload.split())
            if is_valid_name(payload):
                player.name = payload
                replies.add(text=f"You set your name to: {payload}")
            else:
                replies.add(
                    text="❌ Invalid name, the name can only have numbers and letters, and can be up to 16 characters long"
                )


@simplebot.command(name="/me")
def me_cmd(message: Message, replies: Replies) -> None:
    """Show your status."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player:
            return

        now = time.time()
        name = get_name(player)
        if not player.name:
            name += " (set name with /name)"
        if player.state == StateEnum.REST:
            state = "🛌 Resting"
        elif player.state == StateEnum.PLAYING_DICE:
            state = "🎲 Rolling the dice"
        else:
            quest = get_quest(player.state)
            if quest:
                cooldown = (
                    session.query(Cooldown)
                    .filter_by(id=quest.id, player_id=player.id)
                    .first()
                )
                quest_cooldown = human_time_duration(cooldown.ends_at - now)
                state = f"🗺️ Quest: {quest.name}. Back in {quest_cooldown}"
            else:
                state = f"UNKNOWN ({player.state})"
        cooldown = (
            session.query(Cooldown)
            .filter_by(id=StateEnum.REST, player_id=player.id)
            .first()
        )
        if cooldown:
            stamina_cooldown = " ⏰"
            seconds = cooldown.ends_at - now
            if seconds < 60:
                stamina_cooldown += "now"
            else:
                stamina_cooldown += human_time_duration(seconds)
        else:
            stamina_cooldown = ""

        replies.add(
            text=f"""Name: {name}

            🔋Stamina: {player.stamina}/{player.max_stamina}{stamina_cooldown}
            💰{player.gold}

            State:
            {state}

            🗺️ Quests: /quests
            🍺 Tavern: /tavern
            📊 Ranking: /top
            """
        )


@simplebot.command(hidden=True)
def top(message: Message, replies: Replies) -> None:
    """Show the list of scoreboards."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player:
            return

        rankings = [
            "**📊 Ranking**",
            "**Midas's Disciples**\n💰 Top gold collectors\n/top1",
            "**Cauldron Worshipers**\n🍀 Most gold received from the magic cauldron\n/top2",
            "**Luckiest Gamblers**\n🎲 Most wins in dice\n/top3",
        ]
        replies.add(text="\n\n".join(rankings))


@simplebot.command(hidden=True)
def top1(message: Message, replies: Replies) -> None:
    """Top gold collectors."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player:
            return

        is_on_top = False
        text = ""
        for i, player2 in enumerate(
            get_players(session)
            .filter(Player.gold > 0)
            .order_by(Player.gold.desc())
            .limit(15)
        ):
            if player.id == player2.id:
                is_on_top = True
                marker = "#️⃣"
            else:
                marker = "#"
            text += f"{marker}{i+1} {get_name(player2)} {player2.gold}💰\n"
        if not is_on_top and text:
            text += "\n...\n"
            text += f"{get_name(player)} {player.gold}💰"
        if text:
            text = "**💰 Top gold collectors**\n\n" + text
        else:
            text = "Everybody is poor :("
        replies.add(text=text)


@simplebot.command(hidden=True)
def top2(message: Message, replies: Replies) -> None:
    """Most gold received from the magic cauldron."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player:
            return

        is_on_top = False
        text = ""
        for i, rank in enumerate(
            session.query(CauldronRank)
            .filter(CauldronRank.gold > 0)
            .order_by(CauldronRank.gold.desc())
            .limit(15)
        ):
            if player.id == rank.id:
                is_on_top = True
                marker = "#️⃣"
            else:
                marker = "#"
            text += f"{marker}{i+1} {get_name(rank.player)} {rank.gold}💰\n"
        if not is_on_top and text:
            text += "\n...\n"
            gold = player.cauldron_rank.gold if player.cauldron_rank else 0
            text += f"{get_name(player)} {gold}💰"
        if text:
            text = (
                "**🍀 Most gold received from the magic cauldron this year**\n\n" + text
            )
        else:
            text = "Nobody has tossed a coin in the cauldron this year, be the first!"
        replies.add(text=text)


@simplebot.command(hidden=True)
def top3(message: Message, replies: Replies) -> None:
    """Most wins in dice this month."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player:
            return

        is_on_top = False
        text = ""
        for i, rank in enumerate(
            session.query(DiceRank)
            .filter(DiceRank.gold > 0)
            .order_by(DiceRank.gold.desc())
            .limit(15)
        ):
            if player.id == rank.id:
                is_on_top = True
                marker = "#️⃣"
            else:
                marker = "#"
            text += f"{marker}{i+1} {get_name(rank.player)} {rank.gold}💰\n"
        if not is_on_top and text:
            text += "\n...\n"
            gold = player.dice_rank.gold if player.dice_rank else 0
            text += f"{get_name(player)} {gold}💰"
        if text:
            text = "**🎲 Most wins in dice this month**\n\n" + text
        else:
            text = "No one has played dice this month, be the first!"
        replies.add(text=text)


@simplebot.command(hidden=True)
def tavern(message: Message, replies: Replies) -> None:
    """Go to the tavern."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player or not validate_resting(player, replies):
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
    replies.add(text=text, filename=get_image("tavern"))


@simplebot.command(hidden=True)
def dice(bot: DeltaBot, message: Message, replies: Replies) -> None:
    """Play dice in the tavern."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if (
            not player
            or not validate_resting(player, replies)
            or not validate_gold(player, DICE_FEE, replies)
        ):
            return

        play_dice(player, session, bot, replies)


@simplebot.command(hidden=True)
def cauldron(message: Message, replies: Replies) -> None:
    """Toss a coin in the magic cauldron."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player or not validate_resting(player, replies):
            return

        cooldown = get_next_day_cooldown(session)
        if player.cauldron_coin:
            replies.add(
                text=f"You already tossed a coin today, come again tomorrow. (⏰{cooldown})"
            )
        elif validate_gold(player, 1, replies):
            player.gold -= 1
            player.cauldron_coin = 1
            replies.add(
                text=f"You tossed a coin into the cauldron, it disappeared in the pitch black inside of the cauldron without making a sound.\n\n(⏰ Gift in {cooldown})"
            )


@simplebot.command(name="/quests", hidden=True)
def quests_cmd(message: Message, replies: Replies) -> None:
    """Show available quests."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player:
            return

    text = ""
    for quest in quests:
        duration = human_time_duration(quest.duration, rounded=False)
        text += f"**{quest.name}** (⏰{duration}, 🔋{quest.stamina})\n{quest.description}\n/quest_{quest.id}\n\n"
    if not text:
        text = "No available quests at the moment :("
    replies.add(text=text)


@simplebot.command(name="/quest", hidden=True)
def quest_cmd(payload: str, message: Message, replies: Replies) -> None:
    """Start a quest."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player or not validate_resting(player, replies):
            return

        quest = get_quest(int(payload))
        if quest:
            if player.stamina < quest.stamina:
                replies.add(text="Not enough stamina. Come back after you take a rest.")
                return
            now = time.time()
            player.state = quest.id
            session.add(
                Cooldown(id=quest.id, player_id=player.id, ends_at=now + quest.duration)
            )
            player.stamina -= quest.stamina
            if (
                player.stamina < player.max_stamina
                and not session.query(Cooldown)
                .filter_by(id=StateEnum.REST, player_id=player.id)
                .first()
            ):
                session.add(
                    Cooldown(
                        id=StateEnum.REST,
                        player_id=player.id,
                        ends_at=now + STAMINA_COOLDOWN,
                    )
                )
            duration = human_time_duration(quest.duration, rounded=False)
            replies.add(text=f"You will be back in {duration}")
        else:
            replies.add(text="❌ Unknown quest")
