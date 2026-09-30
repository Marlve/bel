# TodoList's per-item removal bookkeeping: the delay before a ticked row
# actually disappears, and the fade Tween that plays it out. Ticket 08 -
# TodoList/TodoCard don't get ADR-0007's full three-file split, just this
# partial extraction; TodoList's own paint/input and TodoCard stay in
# todoCard.py.

from PySide6.QtCore import QTimer

import style
from anims.clock import Tween
from anims import curves


class TodoListAnimation:
    def __init__(self, parent):
        self.parent = parent
        self.remove_timers = {}  # id(item) -> QTimer, ticked rows waiting to auto-remove
        self.remove_fade = {}  # id(item) -> current fade-out alpha, for a row mid-removal
        self.fade_tweens = {}  # id(item) -> its Tween, kept alive while fading

    def scheduleRemoval(self, item):
        """A ticked row is live for a beat in case the tick was a mistake -
        only once it's sat done for TODO_REMOVE_DELAY_MS untouched does it
        actually go. Keyed by the item's identity, not its content, so two
        rows with identical text/done never get their timers mixed up."""
        self.cancelRemoval(item)
        timer = QTimer(self.parent)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self.removeIfStillDone(item))
        timer.start(style.TODO_REMOVE_DELAY_MS)
        self.remove_timers[id(item)] = timer

    def cancelRemoval(self, item):
        timer = self.remove_timers.pop(id(item), None)
        if timer is not None:
            timer.stop()

    def settle(self):
        """Drops every pending timer and fade, so a hide leaves no
        half-removed row behind."""
        for timer in self.remove_timers.values():
            timer.stop()
        self.remove_timers.clear()
        for tween in self.fade_tweens.values():
            tween.stop()
        self.fade_tweens.clear()
        self.remove_fade.clear()

    def removeIfStillDone(self, item):
        self.remove_timers.pop(id(item), None)
        if not item["done"]:
            return  # unticked before the timer fired
        if not self.parent.card.motion:
            self.parent.finishRemoval(item)
            return
        self.remove_fade[id(item)] = 1.0
        tween = Tween(
            self.parent, lambda v, item=item: self.onItemFadeTick(item, v), lambda item=item: self.onItemFadeDone(item)
        )
        self.fade_tweens[id(item)] = tween
        tween.run(1.0, 0.0, style.TODO_ITEM_FADE_MS, curves.CHAT_FLIGHT)

    def onItemFadeTick(self, item, value):
        self.remove_fade[id(item)] = value
        self.parent.update()

    def onItemFadeDone(self, item):
        self.fade_tweens.pop(id(item), None)
        self.remove_fade.pop(id(item), None)
        if not item["done"]:
            return  # unticked mid-fade - stay put
        self.parent.finishRemoval(item)
