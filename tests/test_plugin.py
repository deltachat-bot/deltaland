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

    def test_top(self, mocker) -> None:
        msg = mocker.get_one_reply("/top")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/top")
        assert "❌" not in msg.text

    def test_top1(self, mocker) -> None:
        msg = mocker.get_one_reply("/top1")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/top1")
        assert "❌" not in msg.text

    def test_top2(self, mocker) -> None:
        msg = mocker.get_one_reply("/top2")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/top2")
        assert "❌" not in msg.text

    def test_top3(self, mocker) -> None:
        msg = mocker.get_one_reply("/top3")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/top3")
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

    def test_quest(self, mocker) -> None:
        msg = mocker.get_one_reply("/quest_1")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start")
        assert "❌" not in msg.text

        msg = mocker.get_one_reply("/quest_0")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/quest_1")
        assert "❌" not in msg.text
