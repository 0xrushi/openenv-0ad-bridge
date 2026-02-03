import unittest

from hannibal_api.parsing import parse_entity_ids


class TestParsing(unittest.TestCase):
    def test_parse_entity_ids_single(self):
        self.assertEqual(parse_entity_ids("186"), [186])

    def test_parse_entity_ids_csv(self):
        self.assertEqual(parse_entity_ids("186, 187,188"), [186, 187, 188])

    def test_parse_entity_ids_rejects_empty(self):
        with self.assertRaises(ValueError):
            parse_entity_ids("")

    def test_parse_entity_ids_rejects_non_numeric(self):
        with self.assertRaises(ValueError):
            parse_entity_ids("186,abc")


if __name__ == "__main__":
    unittest.main()
