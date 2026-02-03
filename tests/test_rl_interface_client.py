import json
import unittest
from unittest.mock import Mock

from hannibal_api.rl_interface_client import RLInterfaceClient


class TestRLInterfaceClient(unittest.TestCase):
    def test_step_formats_lines(self):
        client = RLInterfaceClient("http://localhost:6000")

        post = Mock(return_value=json.dumps({"ok": True}))
        client._post = post  # type: ignore[method-assign]

        client.step(
            [(1, {"type": "walk", "entities": [186], "x": 1, "z": 2, "queued": False})]
        )
        args, _kwargs = post.call_args
        self.assertEqual(args[0], "step")
        self.assertIn("1;", args[1])
        self.assertIn('"type":"walk"', args[1])

    def test_move_builds_walk_command(self):
        client = RLInterfaceClient("http://localhost:6000")

        post = Mock(return_value=json.dumps({"state": "ok"}))
        client._post = post  # type: ignore[method-assign]

        out = client.move(player_id=1, entity_ids=[186], x=150, z=200)
        self.assertEqual(out["state"], "ok")

        # Ensure pushFront is present in serialized command.
        args, _kwargs = post.call_args
        self.assertIn('"pushFront":true', args[1])

    def test_walk_postcommand_uses_evaluate(self):
        client = RLInterfaceClient("http://localhost:6000")
        post = Mock(return_value=json.dumps({"ok": True}))
        client._post = post  # type: ignore[method-assign]

        client.walk_postcommand(1, [186], 150, 200)
        args, _kwargs = post.call_args
        self.assertEqual(args[0], "evaluate")
        self.assertIn("Engine.PostCommand(1", args[1])
        self.assertIn('"type":"walk"', args[1])


if __name__ == "__main__":
    unittest.main()
