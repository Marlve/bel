# Global hotkey listener. `keyboard` fires callbacks from its own background
# thread, so we re-emit onto the Qt main thread via a signal instead of
# touching widgets directly from that thread.

import keyboard
from PySide6.QtCore import QObject, Signal


class HotkeyListener(QObject):
    triggered = Signal()

    def __init__(self, hotkey):
        super().__init__()
        self._hotkey = hotkey

    def start(self):
        keyboard.add_hotkey(self._hotkey, self.triggered.emit)
