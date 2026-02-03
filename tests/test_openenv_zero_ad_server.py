import unittest
from unittest.mock import Mock


try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None  # type: ignore[assignment]


from openenv_zero_ad.environment import ZeroADSession
from openenv_zero_ad.server import create_app


@unittest.skipIf(TestClient is None, "fastapi not installed")
class TestOpenEnvZeroADServer(unittest.TestCase):
    def test_reset_returns_openenv_shape(self):
        session = ZeroADSession("http://example.invalid")
        session.rl.evaluate = Mock(return_value=2)  # type: ignore[method-assign]

        times = iter([1.0, 2.0])
        session._get_sim_time = Mock(side_effect=lambda: next(times))  # type: ignore[attr-defined]

        app = create_app(session=session)
        client = TestClient(app)

        resp = client.post("/reset", json={})
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertIn("observation", data)
        self.assertIn("reward", data)
        self.assertIn("done", data)

        obs = data["observation"]
        self.assertTrue(obs["ok"])
        self.assertIsNotNone(obs.get("episode_id"))
        self.assertEqual(obs.get("step_count"), 0)
        self.assertEqual(obs.get("stepper_detected"), True)

    def test_step_evaluate(self):
        session = ZeroADSession("http://example.invalid")
        session.rl.evaluate = Mock(return_value={"x": 123})  # type: ignore[method-assign]
        session._get_sim_time = Mock(return_value=None)  # type: ignore[attr-defined]

        app = create_app(session=session)
        client = TestClient(app)

        resp = client.post(
            "/step",
            json={"action": {"op": "evaluate", "code": "1+1"}},
        )
        self.assertEqual(resp.status_code, 200)
        obs = resp.json()["observation"]
        self.assertTrue(obs["ok"])
        self.assertEqual(obs["result"], {"x": 123})

    def test_step_push_command(self):
        session = ZeroADSession("http://example.invalid")
        session.rl.push_command = Mock(return_value={"ok": True})  # type: ignore[method-assign]
        session.rl.evaluate = Mock(return_value={"ok": True})  # type: ignore[method-assign]
        session._get_sim_time = Mock(return_value=None)  # type: ignore[attr-defined]

        app = create_app(session=session)
        client = TestClient(app)

        resp = client.post(
            "/step",
            json={
                "action": {
                    "op": "push_command",
                    "player_id": 1,
                    "cmd": {"type": "walk", "entities": [1], "x": 1, "z": 2},
                }
            },
        )
        self.assertEqual(resp.status_code, 200)
        obs = resp.json()["observation"]
        self.assertTrue(obs["ok"])
        self.assertEqual(obs["result"], {"ok": True})

    def test_step_push_command_missing_entity_returns_error(self):
        session = ZeroADSession("http://example.invalid")
        session._get_sim_time = Mock(return_value=None)  # type: ignore[attr-defined]

        # Validation happens via rl.evaluate(...)
        session.rl.evaluate = Mock(
            return_value={"ok": False, "missing": [999], "wrongOwner": []}
        )  # type: ignore[method-assign]
        session.rl.push_command = Mock(return_value={"ok": True})  # type: ignore[method-assign]

        app = create_app(session=session)
        client = TestClient(app)

        resp = client.post(
            "/step",
            json={
                "action": {
                    "op": "push_command",
                    "player_id": 1,
                    "cmd": {
                        "type": "walk",
                        "entities": [999],
                        "x": 1,
                        "z": 2,
                        "queued": False,
                        "pushFront": True,
                    },
                }
            },
        )
        self.assertEqual(resp.status_code, 200)
        obs = resp.json()["observation"]
        self.assertFalse(obs["ok"])
        self.assertIn("invalid_entity_ids", obs["error"])
        self.assertIn("999", obs["error"])
        session.rl.push_command.assert_not_called()

    def test_step_push_command_walk_requires_entities(self):
        session = ZeroADSession("http://example.invalid")
        session._get_sim_time = Mock(return_value=None)  # type: ignore[attr-defined]
        session.rl.push_command = Mock(return_value={"ok": True})  # type: ignore[method-assign]

        app = create_app(session=session)
        client = TestClient(app)

        resp = client.post(
            "/step",
            json={
                "action": {
                    "op": "push_command",
                    "player_id": 1,
                    "cmd": {"type": "walk", "entities": [], "x": 1, "z": 2},
                }
            },
        )

        self.assertEqual(resp.status_code, 200)
        obs = resp.json()["observation"]
        self.assertFalse(obs["ok"])
        self.assertIn("walk requires non-empty", obs["error"])
        session.rl.push_command.assert_not_called()

    def test_schema_endpoint(self):
        session = ZeroADSession("http://example.invalid")
        session.rl.evaluate = Mock(return_value=2)  # type: ignore[method-assign]
        session._get_sim_time = Mock(return_value=None)  # type: ignore[attr-defined]

        app = create_app(session=session)
        client = TestClient(app)

        resp = client.get("/schema")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("action", data)
        self.assertIn("observation", data)
        self.assertIn("state", data)


if __name__ == "__main__":
    unittest.main()
