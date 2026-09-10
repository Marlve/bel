# Shared drop-shadow look for the app's floating surfaces - the prompt bar,
# and (once each card makes room for it, see style.CARD_SHADOW_MARGIN) the
# chat/todo/note cards, so they all read as one family the way design.md's
# CHAT_* palette already does.

from PySide6.QtWidgets import QGraphicsDropShadowEffect
from PySide6.QtGui import QColor

import style


def apply(widget):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(style.CARD_SHADOW_BLUR)
    effect.setOffset(0, style.CARD_SHADOW_OFFSET_Y)
    effect.setColor(QColor(0, 0, 0, style.CARD_SHADOW_ALPHA))
    widget.setGraphicsEffect(effect)
