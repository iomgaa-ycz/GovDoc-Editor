from __future__ import annotations

import unittest

from docx_common_text.compare import find_common_segments, find_exact_matches, split_sentences


class CompareTests(unittest.TestCase):
    def test_split_sentences_supports_chinese_and_english(self) -> None:
        paragraphs = [
            "Hello world. This is a test.",
            "\u8fd9\u662f\u7b2c\u4e00\u53e5\u3002\u8fd9\u662f\u7b2c\u4e8c\u53e5\uff01",
        ]

        self.assertEqual(
            split_sentences(paragraphs),
            [
                "Hello world.",
                "This is a test.",
                "\u8fd9\u662f\u7b2c\u4e00\u53e5\u3002",
                "\u8fd9\u662f\u7b2c\u4e8c\u53e5\uff01",
            ],
        )

    def test_find_exact_matches_keeps_positions(self) -> None:
        first_items = ["alpha", "beta", "alpha", "gamma"]
        second_items = ["beta", "delta", "alpha"]

        matches = find_exact_matches(first_items, second_items)

        self.assertEqual(
            [match.text for match in matches],
            ["alpha", "beta"],
        )
        self.assertEqual(matches[0].first_positions, [1, 3])
        self.assertEqual(matches[0].second_positions, [3])
        self.assertEqual(matches[1].first_positions, [2])
        self.assertEqual(matches[1].second_positions, [1])

    def test_find_common_segments_filters_short_matches(self) -> None:
        first_text = "The shared section is here.\nAnd it continues."
        second_text = "Prefix. The shared section is here.\nAnd it continues. Suffix."

        segments = find_common_segments(first_text, second_text, min_length=15)

        self.assertEqual(len(segments), 1)
        self.assertIn("The shared section is here.", segments[0].text)
        self.assertGreaterEqual(segments[0].length, 15)


if __name__ == "__main__":
    unittest.main()
