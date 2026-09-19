# Pure "where is everything at time t" math for the app's animations.
# Nothing here touches a widget: callers feed these an elapsed-ms clock and
# paint whatever they return. Each pose is (1, 1, ...) - the resting pose -
# outside its own phase, so the phases can simply be multiplied.

import math

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor

import style
from . import curves


def progress(elapsed, duration, start=0):
    """Fraction 0..1 of the way through a window of `duration` ms that
    begins `start` ms into the clock."""
    return min(max((elapsed - start) / duration, 0), 1)


def lerp(a, b, t):
    return a + (b - a) * t


def bisector(index, count):
    """Unit vector out through the middle of wedge `index`, in screen space
    (y grows downward). Wedge 0 points up, winding clockwise."""
    angle = math.radians(90 - index * 360 / count)
    return math.cos(angle), -math.sin(angle)


def open_total_ms():
    return style.OPEN_MS


def open_pose(elapsed):
    """(scale, alpha) of a wedge while the ring is arriving. Every wedge
    shares the same clock, so they all pop in together."""
    scale_t = curves.OPEN_SCALE.valueForProgress(progress(elapsed, style.OPEN_MS))
    alpha_t = curves.OPEN_FADE.valueForProgress(progress(elapsed, style.OPEN_FADE_MS))
    return lerp(style.OPEN_SCALE_FROM, 1, scale_t), alpha_t


def hover_pose(t):
    """(push px along the bisector, outer radius px, label scale) for a
    wedge whose hover float is `t`."""
    r = style.RING_RADIUS
    return (
        lerp(0, style.HOVER_PUSH * r, t),
        lerp(r, style.HOVER_GROW * r, t),
        lerp(1, style.LABEL_HOVER_SCALE, t),
    )


def select_total_ms():
    return style.SELECT_OTHERS_MS + style.SELECT_HOLD_MS


def select_pose(elapsed, chosen):
    """(scale, alpha, push px) after a wedge is picked. The others drop away
    over SELECT_OTHERS_MS; the chosen one keeps pushing outward for the whole
    phase so it's alone on screen for the hold before the close begins."""
    if chosen:
        t = curves.SELECT.valueForProgress(progress(elapsed, select_total_ms()))
        return lerp(1, style.SELECT_SCALE, t), 1, lerp(0, style.SELECT_PUSH * style.RING_RADIUS, t)
    t = curves.SELECT.valueForProgress(progress(elapsed, style.SELECT_OTHERS_MS))
    return lerp(1, style.SELECT_OTHERS_SCALE, t), lerp(1, style.SELECT_OTHERS_ALPHA, t), 0


def close_pose(elapsed):
    """(scale, alpha) of the whole ring while it leaves."""
    t = curves.CLOSE.valueForProgress(progress(elapsed, style.CLOSE_MS))
    return lerp(1, style.CLOSE_SCALE_TO, t), lerp(1, 0, t)


# --- Handing off to the prompt bar. One clock covers all three phases:
# the ring exits, a rounded rect grows out of the chosen wedge, and the
# field's chrome fades in once that rect is at rest.


def geometry_rest_ms():
    return style.RING_EXIT_MS + style.GROW_MS


def handoff_total_ms():
    return geometry_rest_ms() + style.FIELD_ARRIVE_MS


def ring_exit_pose(elapsed, chosen):
    """(scale, alpha) of a wedge while the ring clears out. The chosen wedge
    holds its hover pose so the click registers, then cross-fades out under
    the growing rect; the rest collapse once the hold is over."""
    if chosen:
        return 1, 1 - crossfade_progress(elapsed)
    t = curves.RING_EXIT.valueForProgress(
        progress(elapsed, style.RING_EXIT_MS - style.RING_EXIT_HOLD_MS, style.RING_EXIT_HOLD_MS)
    )
    return lerp(1, style.RING_EXIT_SCALE, t), lerp(1, 0, t)


def grow_progress(elapsed):
    return curves.GROW.valueForProgress(progress(elapsed, style.GROW_MS, style.RING_EXIT_MS))


def crossfade_progress(elapsed):
    return progress(elapsed, style.CROSSFADE_MS, style.RING_EXIT_MS)


def field_progress(elapsed):
    return progress(elapsed, style.FIELD_ARRIVE_MS, geometry_rest_ms())


# --- The card's flight to the corner. It starts as the prompt bar's rect
# and squares off into the docked card before it gets there.


def card_flight_progress(elapsed):
    return curves.CHAT_FLIGHT.valueForProgress(progress(elapsed, style.CHAT_FLIGHT_MS))


def card_radius(elapsed, start):
    t = curves.CHAT_FLIGHT.valueForProgress(progress(elapsed, style.CHAT_RADIUS_MS))
    return lerp(start, style.CHAT_RADIUS, t)


def typing_dot_pose(elapsed, period_ms):
    """0..1 brightness for each of the pre-reply typing indicator's 3 dots -
    a sequential pulse, each dot 1/3 of the cycle behind the last, so it
    visibly travels across the row rather than all 3 dots pulsing in
    unison."""
    return tuple((math.sin(2 * math.pi * (elapsed / period_ms - i / 3)) + 1) / 2 for i in range(3))


def lerp_rect(a, b, t):
    return QRectF(
        lerp(a.x(), b.x(), t),
        lerp(a.y(), b.y(), t),
        lerp(a.width(), b.width(), t),
        lerp(a.height(), b.height(), t),
    )


def mix(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor.fromRgbF(
        lerp(a.redF(), b.redF(), t),
        lerp(a.greenF(), b.greenF(), t),
        lerp(a.blueF(), b.blueF(), t),
    )
