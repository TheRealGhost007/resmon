import unittest

from resmon.themes import THEME_COLORS, THEME_IDS, THEME_LABELS, colors_for


class ThemesTests(unittest.TestCase):
    def test_every_theme_id_has_colors_and_a_label(self):
        for theme_id in THEME_IDS:
            self.assertIn(theme_id, THEME_COLORS)
            self.assertIn(theme_id, THEME_LABELS)

    def test_every_theme_defines_the_same_metric_keys(self):
        key_sets = [frozenset(colors.keys()) for colors in THEME_COLORS.values()]
        self.assertEqual(len(set(key_sets)), 1, "themes disagree on which metrics they color")

    def test_colors_are_valid_rgb_tuples(self):
        for colors in THEME_COLORS.values():
            for rgb in colors.values():
                self.assertEqual(len(rgb), 3)
                for channel in rgb:
                    self.assertGreaterEqual(channel, 0.0)
                    self.assertLessEqual(channel, 1.0)

    def test_colors_for_unknown_theme_falls_back_to_default(self):
        self.assertEqual(colors_for("not-a-real-theme"), THEME_COLORS["default"])

    def test_colors_for_known_theme(self):
        self.assertEqual(colors_for("onyx"), THEME_COLORS["onyx"])


if __name__ == "__main__":
    unittest.main()
