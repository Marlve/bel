# Global hotkey listener on Windows' RegisterHotKey: the OS posts WM_HOTKEY to
# the Qt main thread's queue, and a native event filter turns it into `triggered`.

import ctypes
import ctypes.wintypes
import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication

import cardStore

WM_HOTKEY = 0x0312
HOTKEY_ID = 1

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000  # holding the combo fires once, not on every auto-repeat

MODIFIERS = {"ctrl": MOD_CONTROL, "shift": MOD_SHIFT, "alt": MOD_ALT}
VK_SPACE = 0x20
VK_F1 = 0x70

STORE_KEY = "hotkeys"
DEFAULT_HOTKEYS = {"pie": "ctrl+shift+space", "chat": "ctrl+alt+space"}
listeners = {}  # name -> HotkeyListener, filled by main so Settings can rebind them live


def load_hotkeys():
    """The saved combo for each name in DEFAULT_HOTKEYS, the default where none is saved."""
    saved = cardStore.load(STORE_KEY, {})
    return {name: saved.get(name, default) for name, default in DEFAULT_HOTKEYS.items()}


def save_hotkey(name, hotkey):
    cardStore.save(STORE_KEY, {**load_hotkeys(), name: hotkey})


def format_hotkey(hotkey):
    """"ctrl+shift+space" -> "Ctrl+Shift+Space"."""
    return "+".join(part.capitalize() for part in hotkey.split("+"))


def parse_hotkey(hotkey):
    """"ctrl+shift+space" -> (RegisterHotKey modifiers, virtual-key code).
    Keys: space, a-z or f1-f24."""
    *modifier_names, key = hotkey.lower().split("+")
    modifiers = MOD_NOREPEAT
    for name in modifier_names:
        modifiers |= MODIFIERS[name]
    if key == "space":
        vk = VK_SPACE
    elif len(key) == 1:
        vk = ord(key.upper())  # a letter's virtual-key code is its capital's ASCII code
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
        self.registered = False
        self.filter_installed = False

    def start(self):
        """Must run on the Qt main thread: a hotkey registered without a
        window belongs to the thread that registered it."""
        modifiers, vk = parse_hotkey(self.hotkey)
        self.registered = bool(ctypes.windll.user32.RegisterHotKey(None, self.hotkey_id, modifiers, vk))
        if not self.registered:
            print(f"Bel: couldn't register {self.hotkey} - another app (or another Bel) already has it", file=sys.stderr)
            return
        if not self.filter_installed:
            QApplication.instance().installNativeEventFilter(self.filter)
            self.filter_installed = True

    def stop(self):
        if self.registered:
            ctypes.windll.user32.UnregisterHotKey(None, self.hotkey_id)
            self.registered = False

    def rebind(self, hotkey):
        """Switches to `hotkey`. If another app holds it, the old combo is put
        back and this returns False."""
        previous = self.hotkey
        self.stop()
        self.hotkey = hotkey
        self.start()
        if self.registered:
            return True
        self.hotkey = previous
        self.start()
        return False
