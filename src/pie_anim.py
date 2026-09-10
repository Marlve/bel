# Pure "where is everything at time t" math for the pie menu's animations.
# Nothing here touches a widget: pie_menu.py feeds these an elapsed-ms clock
# and paints whatever they return. Each pose is (1, 1, ...) - the resting
# pose - outside its own phase, so the phases can simply be multiplied.

import math

from PySide6.QtCore import QEasingCurve, QRectF

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


def open_total_ms(count):
    return style.OPEN_MS + style.OPEN_STAGGER_MS * (count - 1)


def open_pose(elapsed, index):
    """(scale, alpha) of wedge `index` while the ring is arriving. Wedges
    start one stagger apart so they pop in clockwise from the top."""
    start = index * style.OPEN_STAGGER_MS
    scale_t = OPEN_SCALE.valueForProgress(progress(elapsed, style.OPEN_MS, start))
    alpha_t = OPEN_FADE.valueForProgress(progress(elapsed, style.OPEN_FADE_MS, start))
    return lerp(style.OPEN_SCALE_FROM, 1, scale_t), alpha_t


def scrim_progress(elapsed):
    return progress(elapsed, style.SCRIM_MS)


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
        t = SELECT.valueForProgress(progress(elapsed, select_total_ms()))
        return lerp(1, style.SELECT_SCALE, t), 1, lerp(0, style.SELECT_PUSH * style.RING_RADIUS, t)
    t = SELECT.valueForProgress(progress(elapsed, style.SELECT_OTHERS_MS))
    return lerp(1, style.SELECT_OTHERS_SCALE, t), lerp(1, style.SELECT_OTHERS_ALPHA, t), 0


def close_pose(elapsed):
    """(scale, alpha) of the whole ring while it leaves."""
    t = CLOSE.valueForProgress(progress(elapsed, style.CLOSE_MS))
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
    t = RING_EXIT.valueForProgress(
        progress(elapsed, style.RING_EXIT_MS - style.RING_EXIT_HOLD_MS, style.RING_EXIT_HOLD_MS)
    )
    return lerp(1, style.RING_EXIT_SCALE, t), lerp(1, 0, t)


def grow_progress(elapsed):
    return GROW.valueForProgress(progress(elapsed, style.GROW_MS, style.RING_EXIT_MS))


def crossfade_progress(elapsed):
    return progress(elapsed, style.CROSSFADE_MS, style.RING_EXIT_MS)


def field_progress(elapsed):
    return progress(elapsed, style.FIELD_ARRIVE_MS, geometry_rest_ms())


def lerp_rect(a, b, t):
    return QRectF(
        lerp(a.x(), b.x(), t),
        lerp(a.y(), b.y(), t),
        lerp(a.width(), b.width(), t),
        lerp(a.height(), b.height(), t),
    )
