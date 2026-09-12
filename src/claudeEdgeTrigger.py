# A thin always-on-top strip along one edge of the work area, used to read
# the cursor's distance from that edge without installing a screen-wide
# mouse hook. Costs nothing when the cursor is elsewhere and dies with the
# app - see claude-chat-flow.md's "Proximity without a global hook". Which
# edge (left or right) depends on which corner the chat card is currently
# docked to - see dockCorner.py.

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QCursor
from PySide6.QtCore import Qt, QTimer

import style


class EdgeTrigger(QWidget):
    """Full work-area height, DOCK_TRIGGER_WIDTH wide, painted fully
    transparent and click-through - it only ever reports distance, it never
    intercepts a click meant for whatever is under it."""

    def __init__(self, on_distance, screen, left=False):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.on_distance = on_distance
        self.left = left

        area = screen.availableGeometry()
        if left:
            self.setGeometry(area.x(), area.y(), style.DOCK_TRIGGER_WIDTH, area.height())
            self.edge_x = area.x()
        else:
            self.setGeometry(area.x() + area.width() - style.DOCK_TRIGGER_WIDTH, area.y(), style.DOCK_TRIGGER_WIDTH, area.height())
            self.edge_x = area.x() + area.width()

        # WA_TransparentForMouseEvents means this window never gets its own
        # enter/leave/move events - poll the global cursor instead, cheaply,
        # only while the trigger exists.
        self.poll = QTimer(self)
        self.poll.timeout.connect(self.checkCursor)
        self.poll.start(50)
        self.show()

    def checkCursor(self):
        pos = QCursor.pos()
        if self.geometry().contains(pos):
            distance = pos.x() - self.edge_x if self.left else self.edge_x - pos.x()
            self.on_distance(max(distance, 0))
        else:
            self.on_distance(style.DOCK_DISARM_PX + 1)  # comfortably past disarm - "cursor is elsewhere"

    def stop(self):
        self.poll.stop()
        self.close()
