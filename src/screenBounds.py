# Shared "which screen is this point on, and how far can something span
# before it overflows that screen's own work area" math. floatingCard.py's
# moveNear() and settingsCard.py's byte-identical copy already computed this
# inline; screen-boundaries/01 was about to add two more near-identical
# copies (the ring's anchor clamp, a dragged card's clamp) rather than let a
# fifth copy of the same arithmetic happen.

from PySide6.QtWidgets import QApplication


def available_area(point, margin=0):
    """The work-area rect of whichever screen `point` (global coordinates,
    a QPoint) is on, falling back to the primary screen - inset by `margin`
    on every side so a caller's own clamp naturally keeps that much breathing
    room from the real screen edge."""
    screen = QApplication.screenAt(point) or QApplication.primaryScreen()
    return screen.availableGeometry().adjusted(margin, margin, -margin, -margin)


def clamp(value, low, high):
    return max(low, min(value, high))
