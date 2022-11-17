class TestPlugin:
    def _basic_test(self, cmd: str, mocker, addr="player@example.com") -> None:
        msg = mocker.get_one_reply(cmd, addr=addr)
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/start", addr=addr)
        assert "❌" not in msg.text

        msg = mocker.get_one_reply(cmd, addr=addr)
        assert "❌" not in msg.text

    def test_filter(self, mocker) -> None:
        self._basic_test("hi", mocker)

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
        self._basic_test("/me", mocker)

    def test_battle(self, mocker) -> None:
        self._basic_test("/battle", mocker)

    def test_hit(self, mocker) -> None:
        self._basic_test("/hit", mocker)

    def test_feint(self, mocker) -> None:
        self._basic_test("/feint", mocker)

    def test_parry(self, mocker) -> None:
        self._basic_test("/parry", mocker)

    def test_report(self, mocker) -> None:
        self._basic_test("/report", mocker)

    def test_tops(self, mocker) -> None:
        for i in range(6):
            i = i or ""
            self._basic_test(f"/top{i}", mocker, addr=f"player{i}@example.com")

    def test_tavern(self, mocker) -> None:
        self._basic_test("/tavern", mocker)

    def test_dice(self, mocker) -> None:
        self._basic_test("/dice", mocker)

    def test_cauldron(self, mocker) -> None:
        self._basic_test("/cauldron", mocker)

    def test_quests(self, mocker) -> None:
        self._basic_test("/quests", mocker)

    def test_wander(self, mocker) -> None:
        self._basic_test("/wander", mocker)

    def test_thieve(self, mocker) -> None:
        self._basic_test("/thieve", mocker)

    def test_interfere(self, mocker) -> None:
        self._basic_test("/interfere", mocker)
