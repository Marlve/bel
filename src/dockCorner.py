# Which of the 4 screen corners the chat card is docked to, and the small
# amount of pure geometry that depends only on that choice - shared by
# ChatSlot.dockRect() (the resting OPEN position), ChatCardAnimation's
# HIDDEN/TAB peek math (mirrored to whichever edge the corner sits on), and
# the drag-and-snap gesture (which corner a drop point is nearest to). No Qt
# widgets, so it's testable without a QApplication - QRectF is just a value
# type.

from PySide6.QtCore import QRectF

TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT = "top_left", "top_right", "bottom_left", "bottom_right"


def is_left(corner):
    return corner in (TOP_LEFT, BOTTOM_LEFT)


def is_top(corner):
    return corner in (TOP_LEFT, TOP_RIGHT)


def nearest(point, area):
    """Whichever of the 4 corners `point` (global coords) is closest to
    within `area` (a QRect/QRectF work area) - split at the area's midpoint
    on each axis."""
    left = point.x() < area.x() + area.width() / 2
    top = point.y() < area.y() + area.height() / 2
    if top:
        return TOP_LEFT if left else TOP_RIGHT
    return BOTTOM_LEFT if left else BOTTOM_RIGHT


def rect(corner, area, size, margin):
    """The `size`-square OPEN rect docked into `corner` of `area`, inset
    `margin` px from the two edges it touches."""
    x = area.x() + margin if is_left(corner) else area.x() + area.width() - margin - size
    y = area.y() + margin if is_top(corner) else area.y() + area.height() - margin - size
    return QRectF(x, y, size, size)
