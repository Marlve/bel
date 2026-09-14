import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import claude


class EnsureCardToolShimTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_shim_path = claude.CARD_TOOL_SHIM_PATH
        claude.CARD_TOOL_SHIM_PATH = Path(self.tmp.name) / "bin" / "cardtool.cmd"

    def tearDown(self):
        claude.CARD_TOOL_SHIM_PATH = self.original_shim_path
        self.tmp.cleanup()

    def test_writes_a_shim_that_invokes_card_tool_py(self):
        claude.ensure_card_tool_shim()
        content = claude.CARD_TOOL_SHIM_PATH.read_text()
        self.assertIn(str(claude.CARD_TOOL_PATH), content)
        self.assertIn("python", content)

    def test_creates_the_parent_directory_if_missing(self):
        self.assertFalse(claude.CARD_TOOL_SHIM_PATH.parent.exists())
        claude.ensure_card_tool_shim()
        self.assertTrue(claude.CARD_TOOL_SHIM_PATH.exists())

    def test_rerunning_overwrites_rather_than_erroring(self):
        claude.ensure_card_tool_shim()
        claude.ensure_card_tool_shim()
        self.assertTrue(claude.CARD_TOOL_SHIM_PATH.exists())


if __name__ == "__main__":
    unittest.main()
