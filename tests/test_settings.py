import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from resmon.settings import DEFAULTS, Settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config_dir = Path(tmp.name)
        self.settings_file = config_dir / "settings.json"

        # Settings imports these as plain names, so patch them where they're
        # bound (resmon.settings), not on the paths module they came from.
        for target, value in [
            ("resmon.settings.CONFIG_DIR", config_dir),
            ("resmon.settings.SETTINGS_FILE", self.settings_file),
        ]:
            patcher = mock.patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_defaults_when_no_file_exists(self):
        settings = Settings()
        for key, value in DEFAULTS.items():
            self.assertEqual(settings.get(key), value)

    def test_set_persists_to_disk(self):
        settings = Settings()
        settings.set("theme", "onyx")
        self.assertTrue(self.settings_file.exists())
        on_disk = json.loads(self.settings_file.read_text())
        self.assertEqual(on_disk["theme"], "onyx")

    def test_a_fresh_instance_picks_up_saved_changes(self):
        Settings().set("update_interval_ms", 5000)
        second = Settings()
        self.assertEqual(second.get("update_interval_ms"), 5000)

    def test_corrupt_file_falls_back_to_defaults(self):
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text("{not valid json")
        settings = Settings()
        self.assertEqual(settings.get("theme"), DEFAULTS["theme"])

    def test_unrecognized_keys_in_file_dont_break_loading(self):
        # Forward-compat: an old settings.json from a future version
        # shouldn't crash a load, and known keys should still resolve.
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(json.dumps({"theme": "onyx", "some_future_key": 123}))
        settings = Settings()
        self.assertEqual(settings.get("theme"), "onyx")


if __name__ == "__main__":
    unittest.main()
