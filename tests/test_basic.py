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
    bot_chat = await user.create_contact(await bot.get_config("addr"))
    await init_cli(bot, str(tmp_path))

    await bot_chat.send_text("hello")
    msg = get_next_message(user)
    assert "you have not joined the game yet" in msg.text.lower()

    await bot_chat.send_text("/start_confirm")
    msg = get_next_message(user)
    assert "welcome to deltaland" in msg.text.lower()

    await bot_chat.send_text("hello")
    msg = get_next_message(user)
    assert "you have not joined the game yet" not in msg.text.lower()
    assert "🏅level" not in msg.text.lower()
