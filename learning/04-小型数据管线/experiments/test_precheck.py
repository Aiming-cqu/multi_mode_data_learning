import json
import tempfile
import unittest
from pathlib import Path

from precheck import check_rows


class PrecheckTest(unittest.TestCase):
    def test_real_input(self):
        root = Path(__file__).parent
        good, bad = check_rows(root / "input_error.jsonl")
        self.assertEqual([x["index"] for x in good], list("ABCDE"))
        self.assertEqual([x["index"] for x in bad], ["F"])
        self.assertEqual(bad[0]["error_type"], "FileNotFoundError")

    def test_bad_json_and_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "input.jsonl"
            src.write_text('not-json\n[]\n{"index":""}\n')
            good, bad = check_rows(src)
            self.assertEqual(len(good), 0)
            self.assertEqual(len(bad), 3)

    def test_decode_and_duplicate_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "broken.png").write_text("not an image")
            row = {"index": "X", "text": "test", "images": ["broken.png"]}
            src = root / "input.jsonl"
            src.write_text((json.dumps(row) + "\n") * 2)
            good, bad = check_rows(src)
            self.assertEqual(good, [])
            self.assertEqual(bad[0]["error_type"], "UnidentifiedImageError")
            self.assertIn("index 重复", bad[1]["reason"])


if __name__ == "__main__":
    unittest.main()
