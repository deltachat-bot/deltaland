class TestPlugin:
    def test_filter(self, mocker) -> None:
        msg = mocker.get_one_reply("hi")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("hi")
        assert "❌" not in msg.text

    def test_start(self, mocker) -> None:
        msg = mocker.get_one_reply("/start")
        assert "/me" in msg.text
        assert msg.filename

        msg = mocker.get_one_reply("/start")
        assert "/me" not in msg.text

    def test_name(self, mocker) -> None:
        msg = mocker.get_one_reply("/name test")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/name")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/name @#$%")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/name test")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/name test2")
        assert "❌" in msg.text

    def test_me(self, mocker) -> None:
        msg = mocker.get_one_reply("/me")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/me")
        assert "❌" not in msg.text

    def test_battle_commands(self, mocker) -> None:
        for cmd in ["/battle", "/hit", "/feint", "/parry", "/report"]:
            msg = mocker.get_one_reply(cmd)
            assert "❌" in msg.text

            msg = mocker.get_one_reply("/start")
            assert "❌" not in msg.text

            msg = mocker.get_one_reply(cmd)
            assert "❌" not in msg.text

    def test_tops(self, mocker) -> None:
        for i in range(6):
            i = i or ""
            cmd = "/top{i}"

            msg = mocker.get_one_reply(cmd)
            assert "❌" in msg.text

            msg = mocker.get_one_reply("/start")
            assert "❌" not in msg.text

            msg = mocker.get_one_reply(cmd)
            assert "❌" not in msg.text

    def test_tavern(self, mocker) -> None:
        msg = mocker.get_one_reply("/tavern")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/tavern")
        assert "❌" not in msg.text
        assert msg.filename

    def test_dice(self, mocker) -> None:
        msg = mocker.get_one_reply("/dice")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/dice")
        assert "❌" not in msg.text

    def test_cauldron(self, mocker) -> None:
        msg = mocker.get_one_reply("/cauldron")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/cauldron")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/cauldron")
        assert "❌" not in msg.text

    def test_quests(self, mocker) -> None:
        msg = mocker.get_one_reply("/quests")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/quests")
        assert "❌" not in msg.text

    def test_wander(self, mocker) -> None:
        msg = mocker.get_one_reply("/wander")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/wander")
        assert "❌" not in msg.text

    def test_thieve(self, mocker) -> None:
        msg = mocker.get_one_reply("/thieve")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/thieve")
        assert "❌" not in msg.text

    def test_interfere(self, mocker) -> None:
        msg = mocker.get_one_reply("/interfere")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/interfere")
        assert "❌" not in msg.text
