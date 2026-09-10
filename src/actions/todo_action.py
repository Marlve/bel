# The todo wedge is a toggle, not a spawn (design.md): the card is built
# lazily on first pick, then just shown/hidden after that so it keeps
# whatever position and items the user left it with.

from todo_card import TodoCard


def todo(config):
    card = None

    def toggle():
        nonlocal card
        if card is None:
            card = TodoCard()
        if card.isVisible():
            card.hide()
        else:
            card.open()

    return toggle
