# The named QEasingCurve instances style.py's *_EASING settings build. Built
# once at import time and shared - a QEasingCurve has no per-use state, so
# every clock that wants "the select curve" reaches for this same object.

from PySide6.QtCore import QEasingCurve

import style


def easing(name, overshoot=None):
    curve = QEasingCurve(getattr(QEasingCurve.Type, name))
    if overshoot is not None:
        curve.setOvershoot(overshoot)
    return curve


OPEN_SCALE = easing(style.OPEN_EASING, style.OPEN_OVERSHOOT)
OPEN_FADE = easing(style.OPEN_FADE_EASING)
HOVER_IN = easing(style.HOVER_IN_EASING, style.HOVER_IN_OVERSHOOT)
HOVER_OUT = easing(style.HOVER_OUT_EASING)
SELECT = easing(style.SELECT_EASING)
CLOSE = easing(style.CLOSE_EASING)
RING_EXIT = easing(style.RING_EXIT_EASING)
GROW = easing(style.GROW_EASING)
CHAT_FLIGHT = easing(style.CHAT_FLIGHT_EASING)
CHAT_DOCK_SNAP = easing(style.CHAT_DOCK_SNAP_EASING, style.CHAT_DOCK_SNAP_OVERSHOOT)
CARD_RESIZE_GRIP_HOVER = easing(style.CARD_RESIZE_GRIP_HOVER_EASING)
