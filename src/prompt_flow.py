# The handoff from a chosen wedge into the prompt bar: a rounded rect grows
# out of the wedge's bounding box into the text field's rect, then the field
# itself takes over once the rect is at rest.
#
# PieMenu owns the phase (HANDOFF/PROMPTING), the chosen wedge, its hover
# pin, and the mouse grab - all ring-level state that outlives a single
# handoff. This only knows how to run the flight and the bar that arrives
# from it, the same division of labor as PromptBar's own relationship to
# PieMenu.

from PySide6.QtCore import QPointF, QRectF

import style
from anims import pose
from anims.clock import Clock
from prompt_bar import PromptBar


class PromptFlow:
    def __init__(self, parent, wedge_count, on_tick, on_arrived):
        self.wedge_count = wedge_count
        self.on_tick = on_tick
        self.on_arrived = on_arrived
        self.ms = 0
        self.anchor = QPointF(0, 0)
        self.index = None

        self.clock = Clock(parent, self.onTick, self.onDone)
        self.bar = PromptBar(parent)
        self.bar.warmup()  # pay its first-paint costs now, not on the user's first handoff

    # --- geometry the bar flies between ---

    def wedgeBox(self, anchor, index):
        """The square the bar's rect grows out of, centered on the wedge's
        label."""
        bx, by = pose.bisector(index, self.wedge_count)
        reach = style.RING_LABEL * style.RING_RADIUS
        box = QRectF(0, 0, style.WEDGE_BOX, style.WEDGE_BOX)
        box.moveCenter(QPointF(anchor.x() + reach * bx, anchor.y() + reach * by))
        return box

    def fieldRect(self, anchor):
        rect = QRectF(0, 0, style.FIELD_WIDTH, style.FIELD_HEIGHT)
        rect.moveCenter(anchor)
        return rect

    # --- the flight ---

    def begin(self, anchor, index, wedge, seed, motion):
        self.anchor = anchor
        self.index = index
        self.ms = 0
        self.bar.launch(wedge.placeholder, seed)
        self.bar.setGeometry(self.wedgeBox(anchor, index).toRect())
        self.bar.raise_()
        self.clock.run(pose.handoff_total_ms(), motion)

    def onTick(self, ms):
        self.ms = ms
        grown = pose.lerp_rect(self.wedgeBox(self.anchor, self.index), self.fieldRect(self.anchor), pose.grow_progress(ms))
        self.bar.setGeometry(grown.toRect())
        self.bar.setFlight(pose.crossfade_progress(ms), pose.field_progress(ms))
        if ms >= pose.geometry_rest_ms():
            self.bar.place()  # only now that the rect has stopped moving
        self.on_tick()

    def onDone(self):
        self.bar.place()
        self.bar.takeFocus()
        self.on_arrived()
