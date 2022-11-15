"""hooks, filters and commands definitions."""

import random
import time
from threading import Thread
from typing import TYPE_CHECKING

import simplebot

from .consts import DICE_FEE, RANKS_REQ_LEVEL, CombatTactic, StateEnum
from .cooldown import cooldown_loop
from .dice import play_dice
from .experience import required_exp
from .game import get_next_battle_cooldown, get_next_day_cooldown, init_game
from .migrations import run_migrations
from .orm import (
    BattleRank,
    BattleTactic,
    CauldronCoin,
    CauldronRank,
    Cooldown,
    DiceRank,
    Player,
    SentinelRank,
    init,
    session_scope,
)
from .quests import get_quest, quests
from .util import (
    calculate_interfere_gold,
    get_battle_result,
    get_database_path,
    get_image,
    get_player,
    get_players,
    human_time_duration,
    is_valid_name,
    notify_level_up,
    send_message,
    setdefault,
    validate_gold,
    validate_level,
    validate_resting,
)

if TYPE_CHECKING:
    from deltachat import Message
    from simplebot.bot import DeltaBot, Replies


@simplebot.hookimpl
def deltabot_init(bot: "DeltaBot") -> None:
    setdefault(bot, "max_players", "0")
    for quest in quests:
        bot.commands.register(
            quest.command, name=quest.command_name, help=quest.description, hidden=True
        )


@simplebot.hookimpl
def deltabot_start(bot: "DeltaBot") -> None:
    run_migrations(bot)
    init(f"sqlite:///{get_database_path(bot)}")
    init_game()
    Thread(target=cooldown_loop, args=(bot,), daemon=True).start()


@simplebot.filter
def filter_messages(message: "Message", replies: "Replies") -> None:
    """Deltaland bot.

    A game-bot that allows you to join the deltaland world and play with people all over the world.
    """
    if not message.chat.is_multiuser():
        me_cmd(message, replies)


@simplebot.command
def start(bot: "DeltaBot", message: "Message", replies: "Replies") -> None:
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
def name_cmd(payload: str, message: "Message", replies: "Replies") -> None:
    """Set your name."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player or not validate_resting(player, replies, session):
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
def me_cmd(message: "Message", replies: "Replies") -> None:
    """Show your status."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player:
            return

        now = time.time()
        name = player.get_name()
        if not player.name:
            name += " (set name with /name)"
        if player.state == StateEnum.REST:
            if player.battle_tactic:
                state = "🏰 Defending the castle"
            else:
                state = "🛌 Resting"
        elif player.state == StateEnum.PLAYING_DICE:
            state = "🎲 Rolling the dice"
        elif player.state == StateEnum.SPOTTED_THIEF:
            state = "👀 noticed thief"
        else:
            quest = get_quest(player.state)
            if quest:
                cooldown = (
                    session.query(Cooldown)
                    .filter_by(id=quest.id, player_id=player.id)
                    .first()
                )
                quest_cooldown = human_time_duration(cooldown.ends_at - now)
                state = f"{quest.status_msg}. Back in {quest_cooldown}"
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
        battle_cooldown = get_next_battle_cooldown(session)

        rankings = "📊 Ranking: /top" if player.level >= RANKS_REQ_LEVEL else ""
        replies.add(
            text=f"""Goblin attack in {battle_cooldown}!

            {name}
            🏅Level: {player.level}
            ⚔️Atk: {player.attack}  🛡️Def: {player.defense}
            🔥Exp: {player.exp}/{required_exp(player.level+1)}
            ❤️HP: {player.hp}/{player.max_hp}
            🔋Stamina: {player.stamina}/{player.max_stamina}{stamina_cooldown}
            💰{player.gold}

            State:
            {state}

            ⚔️ Battle: /battle
            🗺️ Quests: /quests
            🍺 Tavern: /tavern
            {rankings}
            """
        )


@simplebot.command(hidden=True)
def battle(message: "Message", replies: "Replies") -> None:
    """Choose battle tactics."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player and not validate_resting(
            player, replies, session, ignore_battle=True
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
    replies.add(text=text)


@simplebot.command(hidden=True)
def hit(message: "Message", replies: "Replies") -> None:
    """Choose HIT as battle tactic."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player and not validate_resting(
            player, replies, session, ignore_battle=True
        ):
            return

        player.battle_tactic = BattleTactic(tactic=CombatTactic.HIT)
        battle_cooldown = get_next_battle_cooldown(session)
        text = (
            "So you will use **🗡️HIT** in the next battle, that sounds like a good plan."
            f" You joined the defensive formations. The next battle is in {battle_cooldown}."
        )
        replies.add(text=text)


@simplebot.command(hidden=True)
def feint(message: "Message", replies: "Replies") -> None:
    """Choose FEINT as battle tactic."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player and not validate_resting(
            player, replies, session, ignore_battle=True
        ):
            return

        player.battle_tactic = BattleTactic(tactic=CombatTactic.FEINT)
        battle_cooldown = get_next_battle_cooldown(session)
        text = (
            "So you will use **💥FEINT** in the next battle, that sounds like a good plan."
            f" You joined the defensive formations. The next battle is in {battle_cooldown}."
        )
        replies.add(text=text)


@simplebot.command(hidden=True)
def parry(message: "Message", replies: "Replies") -> None:
    """Choose PARRY as battle tactic."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player and not validate_resting(
            player, replies, session, ignore_battle=True
        ):
            return

        player.battle_tactic = BattleTactic(tactic=CombatTactic.PARRY)
        battle_cooldown = get_next_battle_cooldown(session)
        text = (
            "So you will use **⚔️PARRY** in the next battle, that sounds like a good plan."
            f" You joined the defensive formations. The next battle is in {battle_cooldown}."
        )
        replies.add(text=text)


@simplebot.command(hidden=True)
def report(message: "Message", replies: "Replies") -> None:
    """Show your last results in the battlefield."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player:
            return
        if not player.battle_report:
            replies.add(text="You were not in the town in the last battle.")
        else:
            replies.add(text=get_battle_result(player), filename=get_image("goblin"))


@simplebot.command(hidden=True)
def top(message: "Message", replies: "Replies") -> None:
    """Show the list of scoreboards."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player or not validate_level(player, RANKS_REQ_LEVEL, replies):
            return

    rankings = [
        "**📊 Ranking**",
        "**Goblin Slayers**\n⚔️ Most victories in the battlefield\n/top1",
        "**Midas's Disciples**\n💰 Top gold collectors\n/top2",
        "**Cauldron Worshipers**\n🍀 Most gold received from the magic cauldron\n/top3",
        "**Luckiest Gamblers**\n🎲 Most wins in dice\n/top4",
        "**Royal Guards**\n🗡️ Most thieves stopped\n/top5",
    ]
    replies.add(text="\n\n".join(rankings))


@simplebot.command(hidden=True)
def top1(message: "Message", replies: "Replies") -> None:
    """Most victories in the battlefield."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player or not validate_level(player, RANKS_REQ_LEVEL, replies):
            return

        is_on_top = False
        text = ""
        for i, rank in enumerate(
            session.query(BattleRank).order_by(BattleRank.victories.desc()).limit(15)
        ):
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
        replies.add(text=text)


@simplebot.command(hidden=True)
def top2(message: "Message", replies: "Replies") -> None:
    """Top gold collectors."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player or not validate_level(player, RANKS_REQ_LEVEL, replies):
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
            text += f"{marker}{i+1} {player2.get_name()} {player2.gold}💰\n"
        if not is_on_top and text:
            text += "\n...\n"
            text += f"{player.get_name()} {player.gold}💰"
        if text:
            text = "**💰 Top gold collectors**\n\n" + text
        else:
            text = "Nobody has gold :("
        replies.add(text=text)


@simplebot.command(hidden=True)
def top3(message: "Message", replies: "Replies") -> None:
    """Most gold received from the magic cauldron."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player or not validate_level(player, RANKS_REQ_LEVEL, replies):
            return

        is_on_top = False
        text = ""
        for i, rank in enumerate(
            session.query(CauldronRank).order_by(CauldronRank.gold.desc()).limit(15)
        ):
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
            text = (
                "**🍀 Most gold received from the magic cauldron this year**\n\n" + text
            )
        else:
            text = "Nobody has received gold from the magic cauldron this year"
        replies.add(text=text)


@simplebot.command(hidden=True)
def top4(message: "Message", replies: "Replies") -> None:
    """Most wins in dice this month."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player or not validate_level(player, RANKS_REQ_LEVEL, replies):
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
            text += f"{marker}{i+1} {rank.player.get_name()} {rank.gold}💰\n"
        if not is_on_top and text:
            text += "\n...\n"
            gold = player.dice_rank.gold if player.dice_rank else 0
            text += f"{player.get_name()} {gold}💰"
        if text:
            text = "**🎲 Most wins in dice this month**\n\n" + text
        else:
            text = "Nobody has earned gold playing dice this month"
        replies.add(text=text)


@simplebot.command(hidden=True)
def top5(message: "Message", replies: "Replies") -> None:
    """Most thieves stopped."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player or not validate_level(player, RANKS_REQ_LEVEL, replies):
            return

        is_on_top = False
        text = ""
        for i, rank in enumerate(
            session.query(SentinelRank).order_by(SentinelRank.stopped.desc()).limit(15)
        ):
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
        replies.add(text=text)


@simplebot.command(hidden=True)
def tavern(message: "Message", replies: "Replies") -> None:
    """Go to the tavern."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player or not validate_resting(player, replies, session):
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
def dice(bot: "DeltaBot", message: "Message", replies: "Replies") -> None:
    """Play dice in the tavern."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if (
            not player
            or not validate_resting(player, replies, session)
            or not validate_gold(player, DICE_FEE, replies)
        ):
            return

        play_dice(player, session, bot, replies)


@simplebot.command(hidden=True)
def cauldron(message: "Message", replies: "Replies") -> None:
    """Toss a coin in the magic cauldron."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player or not validate_resting(player, replies, session):
            return

        cooldown = get_next_day_cooldown(session)
        if player.cauldron_coin:
            replies.add(
                text=f"You already tossed a coin, come again later. (⏰{cooldown})"
            )
        elif validate_gold(player, 1, replies):
            player.gold -= 1
            player.cauldron_coin = CauldronCoin()
            replies.add(
                text=f"You tossed a coin into the cauldron, it disappeared in the pitch black inside of the cauldron without making a sound.\n\n(⏰ Gift in {cooldown})"
            )


@simplebot.command(name="/quests", hidden=True)
def quests_cmd(message: "Message", replies: "Replies") -> None:
    """Show available quests."""
    with session_scope() as session:
        player = get_player(session, message, replies)
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
    replies.add(text=text)


@simplebot.command(hidden=True)
def interfere(bot: "DeltaBot", message: "Message", replies: "Replies") -> None:
    """Stop a thief."""
    with session_scope() as session:
        player = get_player(session, message, replies)
        if not player:
            return

        if player.thief:
            thief = player.thief

            player.stop_spotting()
            if not player.sentinel_rank:
                player.sentinel_rank = SentinelRank(stopped=0)
            player.sentinel_rank.stopped += 1
            player_gold = calculate_interfere_gold(player)
            player.gold += player_gold
            player_exp = random.randint(1, 3)
            if player.increase_exp(player_exp):  # level up
                notify_level_up(bot, player)
            text = (
                "You called the town's guards and charged at the thief."
                f" **{thief.get_name()}** fled but not before receiving one of your blows."
                " The townsmen gave you some gold coins as reward.\n\n"
                f"💰Gold: {player_gold:+}\n"
                f"🔥Exp: {player_exp:+}\n"
            )
            replies.add(text=text)

            thief_gold = -min(calculate_interfere_gold(thief), thief.gold)
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
            send_message(bot, thief.id, text=text)
        else:
            replies.add(text="Too late. Action is not available")


@simplebot.command(admin=True)
def delete_player(payload: str, replies: "Replies") -> None:
    """Delete a player account.

    /delete_player 10
    """
    player_id = int(payload)
    with session_scope() as session:
        player = session.query(Player).filter_by(id=player_id).first()
        if player:
            session.delete(player)
            replies.add(text=f"Player({player_id}) deleted")
        else:
            replies.add(text=f"❌ Unknown player: {player_id}")


@simplebot.command(admin=True)
def search_player(payload: str, replies: "Replies") -> None:
    """Delete a player account.

    /delete_player 10
    """
    with session_scope() as session:
        text = ""
        for player in session.query(Player).filter_by(name=payload):
            text += f"ID: {player.id}\n"
        if text:
            replies.add(text=f"Search result for {payload!r}:\n\n" + text)
        else:
            replies.add(text=f"❌ No matches for: {payload}")


@simplebot.command(name="/player_gold", admin=True)
def player_gold_cmd(args: list, replies: "Replies") -> None:
    """Add or substract gold to player.

    /player_gold 10 +20
    """
    player_id, gold = args[0], _parse_number(args[1])
    with session_scope() as session:
        player = session.query(Player).filter_by(id=player_id).first()
        if player:
            player.gold = max(0, player.gold + gold)
            replies.add(text=f"Player({player_id}) gold: {player.gold}")
        else:
            replies.add(text=f"❌ Unknown player: {player_id}")


def _parse_number(numb: str) -> int:
    if not numb.startswith(("-", "+")):
        return 0
    try:
        return int(numb)
    except ValueError:
        return 0
