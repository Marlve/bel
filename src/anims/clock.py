# QVariantAnimation subclasses every widget's clocks are built from.
#
# Clock ticks in raw elapsed ms, so a pose function that derives several
# properties from one time source (anims/pose.py) has something to feed.
# Tween is the more common case: a single property with nothing else riding
# on the same clock, so Qt's own start/end/duration/easing interpolation is
# enough - no pose function needed at all.

from PySide6.QtCore import QVariantAnimation

import style
from . import curves


class Clock(QVariantAnimation):
    """An elapsed-ms clock. Feeds `on_tick(ms)` on every step and
    `on_done()` once it reaches its end value."""

    def __init__(self, parent, on_tick, on_done):
        super().__init__(parent)
        self.setStartValue(0)
        self.valueChanged.connect(on_tick)
        self.finished.connect(on_done)

    def run(self, total_ms, motion=True):
        self.setEndValue(total_ms)
        self.setDuration(total_ms)
        self.start()
        if not motion:
            self.setCurrentTime(total_ms)  # jump straight to the resting pose


class Tween(QVariantAnimation):
    """A plain value-to-value animation: Qt interpolates and eases `start`
    to `end` itself, handing the already-eased value to `on_tick`."""

    def __init__(self, parent, on_tick, on_done=None):
        super().__init__(parent)
        self.valueChanged.connect(on_tick)
        if on_done is not None:
            self.finished.connect(on_done)

    def run(self, start, end, duration_ms, easing=None):
        # stop() leaves currentTime at wherever the previous run ended, so
        # setStartValue/setEndValue below recompute currentValue at that
        # stale progress and fire a spurious valueChanged - jumping to the
        # new end value, then snapping to the new start value once start()
        # resets currentTime to 0. Block those two fake ticks; only the
        # real, eased ones should reach on_tick.
        self.stop()
        self.blockSignals(True)
        self.setStartValue(start)
        self.setEndValue(end)
        self.setDuration(duration_ms)
        if easing is not None:
            self.setEasingCurve(easing)
        self.blockSignals(False)
        self.start()


class HoverClock(Tween):
    """One wedge's 0..1 hover float. animateTo() picks the hover-in or
    hover-out timing depending on which way it's headed, or - with motion
    off - jumps straight there without animating at all."""

    def __init__(self, parent, on_tick):
        super().__init__(parent, on_tick)
        self._on_tick = on_tick

    def animateTo(self, current, target, motion=True):
        self.stop()
        if not motion:
            self._on_tick(float(target))
            return
        duration, curve = (
            (style.HOVER_IN_MS, curves.HOVER_IN) if target else (style.HOVER_OUT_MS, curves.HOVER_OUT)
        )
        self.run(current, float(target), duration, curve)
