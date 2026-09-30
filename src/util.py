import ctypes

import cardStore

SPI_GETCLIENTAREAANIMATION = 0x1042
MOTION_STORE_KEY = "motion"


def reduced_motion():
    """True when Windows' "Show animations" accessibility setting is off, or
    Bel's own Reduce motion switch in Settings is on."""
    enabled = ctypes.c_int(1)
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(enabled), 0)
    return not enabled.value or reduce_motion_setting()


_reduce_setting = None  # read from disk once - motion is asked on every hover


def reduce_motion_setting():
    global _reduce_setting
    if _reduce_setting is None:
        _reduce_setting = bool(cardStore.load(MOTION_STORE_KEY, {}).get("reduce", False))
    return _reduce_setting


def save_reduce_motion_setting(reduce):
    global _reduce_setting
    _reduce_setting = bool(reduce)
    cardStore.save(MOTION_STORE_KEY, {"reduce": _reduce_setting})


class LiveMotion:
    """A `motion` flag that follows reduced_motion() on every read, so the
    Settings switch (or Windows') takes effect on an open card at once,
    until something assigns `motion` explicitly."""

    motion_override = None

    @property
    def motion(self):
        return self.motion_override if self.motion_override is not None else not reduced_motion()

    @motion.setter
    def motion(self, value):
        self.motion_override = value


def force_foreground(hwnd):
    """Force window `hwnd` to the OS foreground so it actually receives
    keyboard input. Windows blocks a background process (Bel, summoned by a
    global hotkey while some other app is focused) from calling
    SetForegroundWindow directly - this is the standard
    workaround: briefly attach our input thread to the current foreground
    window's, which Windows treats as permission to activate.
    """
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    foreground_hwnd = user32.GetForegroundWindow()
    foreground_thread = user32.GetWindowThreadProcessId(foreground_hwnd, None)
    current_thread = kernel32.GetCurrentThreadId()

    if foreground_thread and foreground_thread != current_thread:
        user32.AttachThreadInput(foreground_thread, current_thread, True)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(foreground_thread, current_thread, False)
    else:
        user32.SetForegroundWindow(hwnd)
