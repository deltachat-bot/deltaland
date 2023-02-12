from argparse import Namespace
from unittest.mock import MagicMock

import pytest
from deltabot_cli import EventType

from deltaland.hooks import cli


async def init_cli(bot, config_dir):
    args = Namespace(config_dir=config_dir)
    bot.add_hooks(cli._hooks)
    await cli._on_init(bot, args)
    await cli._on_start(bot, args)


async def get_next_message(account):
    while True:
        event = await account.wait_for_event()
        if event.type == EventType.INCOMING_MSG:
            message = account.get_message_by_id(event.msg_id)
            break
    return await message.get_snapshot()


@pytest.mark.asyncio
async def test_filter(acfactory, tmp_path) -> None:
    user = (await acfactory.get_online_accounts(1))[0]
    bot = await acfactory.new_configured_bot()
    bot_chat = await (
        await user.create_contact(await bot.account.get_config("addr"))
    ).create_chat()
    await init_cli(bot, str(tmp_path))
    NOT_JOINED = "you have not joined the game yet"

    await bot_chat.send_text("hello")
    msg = await get_next_message(user)
    assert NOT_JOINED in msg.text.lower()

    await bot_chat.send_text("/start_confirm")
    msg = await get_next_message(user)
    assert "welcome to deltaland" in msg.text.lower()

    await bot_chat.send_text("hello")
    msg = await get_next_message(user)
    assert NOT_JOINED not in msg.text.lower()
    assert "🏅level" not in msg.text.lower()
