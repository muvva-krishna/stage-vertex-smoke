import json
import tempfile
import unittest
from pathlib import Path

from debev_config.migration import migrate_file


class MigrationPublicTests(unittest.TestCase):
    def test_v1_config_migrates_and_keeps_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "endpoint": "https://service.example",
                "retries": 5,
                "preferences": {"theme": "dark"},
            }))
            result = migrate_file(path)
            self.assertEqual(result["schema_version"], 2)
            self.assertEqual(result["retry"]["max_attempts"], 5)
            self.assertEqual(result["extensions"]["theme"], "dark")

    def test_completed_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "endpoint": "https://service.example",
                "retries": 2,
                "preferences": {"plugin": {"enabled": True}},
            }))
            first = migrate_file(path)
            second = migrate_file(path)
            self.assertEqual(second, first)


if __name__ == "__main__":
    unittest.main()
