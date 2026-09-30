# The ring's wedge shape and hit-test, shared by the pie menu itself and Settings' preview of it.

import math

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath


def ring_segment(outer, inner, start_angle, span):
    """Annular sector centered on the origin. Angles are Qt's: degrees,
    0 = right, growing counter-clockwise."""
    outer_rect = QRectF(-outer, -outer, outer * 2, outer * 2)
    inner_rect = QRectF(-inner, -inner, inner * 2, inner * 2)
    path = QPainterPath()
    path.arcMoveTo(outer_rect, start_angle)
    path.arcTo(outer_rect, start_angle, span)
    path.arcTo(inner_rect, start_angle + span, -span)
    path.closeSubpath()
    return path


def wedge_index(dx, dy, count, deadzone=0, radius=None):
    """Index of the wedge (0 = up, going clockwise) that (dx, dy) points
    into, or None if the point is inside the deadzone or outside radius.
    dx/dy are a screen space offset from the menu's center - y grows
    downward.
    """
    dist = math.hypot(dx, dy)
    if dist < deadzone:
        return None
    if radius is not None and dist > radius:
        return None

    math_angle = math.degrees(math.atan2(-dy, dx)) % 360  # 0=right, 90=up
    compass_angle = (90 - math_angle) % 360  # 0=up, 90=right, clockwise
    wedge_width = 360 / count
    shifted = (compass_angle + wedge_width / 2) % 360
    return int(shifted // wedge_width)
