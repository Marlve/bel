import ctypes

SPI_GETCLIENTAREAANIMATION = 0x1042


def reduced_motion():
    """True when Windows' "Show animations" accessibility setting is off."""
    enabled = ctypes.c_int(1)
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(enabled), 0)
    return not enabled.value


def force_foreground(hwnd):
    """Force window `hwnd` to the OS foreground so it actually receives
    keyboard input. Windows blocks a background process (our global hotkey
    listener runs on its own thread, unrelated to whatever app is focused)
    from calling SetForegroundWindow directly - this is the standard
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
