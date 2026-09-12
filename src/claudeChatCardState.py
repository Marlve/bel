# The chat card's conversation data - session id, turn count, the request
# in flight, and the transcript itself. Pure Python, no Qt: claudeChatCard.py
# (view) and claudeChatCardAnimation.py read and write these fields
# directly, the same way EdgeDockDriver reads/writes EdgeDock.
# dock_rect is this card's OPEN geometry - fixed until a drag-and-snap picks
# a new corner (claudeChatCardAnimation.py's dockToCorner()), which updates
# both dock_rect and corner together.

import dockCorner


class ChatCardState:
    def __init__(self, dock_rect, corner=dockCorner.TOP_RIGHT):
        self.dock_rect = dock_rect
        self.corner = corner
        self.wedge_id = None
        self.action = None
        self.session_id = None
        self.turn_count = 0  # messages sent in the current session; capped, see ChatCard.send()
        self.request = None
        self.buffered = ""
        self.turns = []  # {"role": "user"/"claude", "text": ...}, one per transcript row
        self.streaming_text = ""
