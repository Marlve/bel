# The text field's named mode - the one bit of state PromptBar tracks
# beyond Qt. promptBar.py (view) and promptBarAnimation.py read and write
# this the same way EdgeDockDriver reads/writes EdgeDock.

EMPTY, TYPING, SENDING, REJECTED = "empty", "typing", "sending", "rejected"


class PromptBarState:
    def __init__(self):
        self.state = EMPTY
