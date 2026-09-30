# Global hotkey listener on Windows' RegisterHotKey: the OS posts WM_HOTKEY to
# the Qt main thread's queue, and a native event filter turns it into `triggered`.

import ctypes
import ctypes.wintypes
import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication

WM_HOTKEY = 0x0312
HOTKEY_ID = 1

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000  # holding the combo fires once, not on every auto-repeat

MODIFIERS = {"ctrl": MOD_CONTROL, "shift": MOD_SHIFT, "alt": MOD_ALT}
VK_SPACE = 0x20
VK_F1 = 0x70


def parse_hotkey(hotkey):
    """"ctrl+shift+space" -> (RegisterHotKey modifiers, virtual-key code).
    Keys: space or f1-f24."""
    *modifier_names, key = hotkey.lower().split("+")
    modifiers = MOD_NOREPEAT
    for name in modifier_names:
        modifiers |= MODIFIERS[name]
    if key == "space":
        vk = VK_SPACE
    else:
        vk = VK_F1 + int(key.removeprefix("f")) - 1
    return modifiers, vk


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, on_hotkey, hotkey_id=HOTKEY_ID):
        super().__init__()
        self.on_hotkey = on_hotkey
        self.hotkey_id = hotkey_id

    def nativeEventFilter(self, event_type, message):
        msg = ctypes.wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
            self.on_hotkey()
            return True, 0
        return False, 0


class HotkeyListener(QObject):
    triggered = Signal()

    def __init__(self, hotkey, hotkey_id=HOTKEY_ID):
        super().__init__()
        self.hotkey = hotkey
        self.hotkey_id = hotkey_id  # one per listener, so two combos don't answer each other
        self.filter = HotkeyFilter(self.triggered.emit, hotkey_id)

    def start(self):
        """Must run on the Qt main thread: a hotkey registered without a
        window belongs to the thread that registered it."""
        modifiers, vk = parse_hotkey(self.hotkey)
        if not ctypes.windll.user32.RegisterHotKey(None, self.hotkey_id, modifiers, vk):
            print(f"Bel: couldn't register {self.hotkey} - another app (or another Bel) already has it", file=sys.stderr)
            return
        QApplication.instance().installNativeEventFilter(self.filter)
