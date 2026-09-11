# The ring's clocks - open/select/close phase timing plus the per-wedge
# hover floats - and the tick-fed values (open_ms/select_ms/close_ms/
# hover_t) the view paints from. Never painted directly: writes into
# PieMenuState the same way EdgeDockDriver reads/writes EdgeDock, and
# reaches back into the view only through the callbacks passed in here
# (scheduling a repaint, restoring window opacity once closed) rather than
# owning any Qt widget itself.

from anims.clock import Clock, HoverClock
from pieMenuState import HIDDEN, OPEN
from util import reduced_motion


class PieMenuAnimation:
    def __init__(self, parent, state, wedge_count, prompt_flow_clock, request_repaint, on_select_done, on_closed):
        self.state = state
        self.request_repaint = request_repaint
        self.on_closed = on_closed
        self.motion = not reduced_motion()

        # Elapsed ms into each phase. A phase that hasn't run sits at 0,
        # where its pose is the resting one, so they all just multiply
        # together in paintWedge without any "has this started yet" branches.
        self.open_ms = 0
        self.select_ms = 0
        self.close_ms = 0
        self.open_clock = Clock(parent, self.onOpenTick, self.onOpened)
        self.select_clock = Clock(parent, self.onSelectTick, on_select_done)
        self.close_clock = Clock(parent, self.onCloseTick, self.onClosed)
        self.clocks = (self.open_clock, self.select_clock, prompt_flow_clock, self.close_clock)

        # One 0..1 float per wedge drives every hover property, so a wedge
        # caught mid-retreat animates from wherever it actually is.
        self.hover_t = [0.0] * wedge_count
        self.hover_anims = [HoverClock(parent, self.makeHoverTick(i)) for i in range(wedge_count)]

    def stopClocks(self):
        # Every phase change calls this. A clock left running would keep
        # ticking into the new phase and, worse, still fire its finished
        # handler - which for select_clock means running the chosen wedge's
        # action a second time.
        for clock in self.clocks:
            clock.stop()

    def makeHoverTick(self, index):
        return lambda t: self.onHoverTick(index, t)

    def onHoverTick(self, index, t):
        self.hover_t[index] = t
        self.request_repaint()

    def animateHover(self, index, target):
        self.hover_anims[index].animateTo(self.hover_t[index], target, self.motion)

    def clearHover(self):
        for anim in self.hover_anims:
            anim.stop()
        self.hover_t = [0.0] * len(self.hover_anims)

    def onOpenTick(self, ms):
        self.open_ms = ms
        self.request_repaint()

    def onOpened(self):
        self.state.phase = OPEN

    def onSelectTick(self, ms):
        self.select_ms = ms
        self.request_repaint()

    def onCloseTick(self, ms):
        self.close_ms = ms
        self.request_repaint()

    def onClosed(self):
        self.state.phase = HIDDEN
        self.on_closed()
