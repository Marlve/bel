# Pure geometry for the ADR-0006 pie menu concept, kept separate from Qt so
# the angle math can be unit tested without spinning up a widget.

import math


def wedge_index(dx, dy, count, deadzone=0):
    """Index of the wedge (0 = up, going clockwise) that (dx, dy) points
    into, or None if the point is inside the deadzone. dx/dy are a screen
    space offset from the menu's center - y grows downward.
    """
    if math.hypot(dx, dy) < deadzone:
        return None

    math_angle = math.degrees(math.atan2(-dy, dx)) % 360  # 0=right, 90=up
    compass_angle = (90 - math_angle) % 360  # 0=up, 90=right, clockwise
    wedge_width = 360 / count
    shifted = (compass_angle + wedge_width / 2) % 360
    return int(shifted // wedge_width)
