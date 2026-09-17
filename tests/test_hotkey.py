import contextlib
import ctypes
import ctypes.wintypes
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import hotkey
from hotkey import HotkeyListener, parse_hotkey


def hotkey_message(message, wparam):
    msg = ctypes.wintypes.MSG()
    msg.message = message
    msg.wParam = wparam
    return msg


class ParseHotkeyTests(unittest.TestCase):
    def test_modifiers_and_key(self):
        self.assertEqual(
            parse_hotkey("ctrl+shift+space"),
            (hotkey.MOD_CONTROL | hotkey.MOD_SHIFT | hotkey.MOD_NOREPEAT, hotkey.VK_SPACE),
        )

    def test_function_key_and_alt(self):
        self.assertEqual(parse_hotkey("alt+f12"), (hotkey.MOD_ALT | hotkey.MOD_NOREPEAT, hotkey.VK_F1 + 11))


class HotkeyListenerTests(unittest.TestCase):
    def setUp(self):
        self.listener = HotkeyListener("ctrl+alt+shift+f12")
        self.fired = []
        self.listener.triggered.connect(lambda: self.fired.append(True))

    def deliver(self, msg):
        return self.listener.filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))

    def test_wm_hotkey_for_this_listener_triggers(self):
        self.deliver(hotkey_message(hotkey.WM_HOTKEY, hotkey.HOTKEY_ID))
        self.assertEqual(self.fired, [True])

    def test_other_messages_are_ignored(self):
        self.deliver(hotkey_message(hotkey.WM_HOTKEY + 1, hotkey.HOTKEY_ID))
        self.deliver(hotkey_message(hotkey.WM_HOTKEY, hotkey.HOTKEY_ID + 1))
        self.assertEqual(self.fired, [])

    def test_a_combo_another_app_holds_warns_instead_of_failing_silently(self):
        user32 = ctypes.windll.user32
        modifiers, vk = parse_hotkey("ctrl+alt+shift+f12")
        self.assertTrue(user32.RegisterHotKey(None, 99, modifiers, vk))
        try:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.listener.start()
            self.assertIn("ctrl+alt+shift+f12", stderr.getvalue())
        finally:
            user32.UnregisterHotKey(None, 99)


if __name__ == "__main__":
    unittest.main()
