# Same toggle shape as the todo wedge - see todoAction.py.

from noteCard import NoteCard


def note(config):
    card = None

    def toggle():
        nonlocal card
        if card is None:
            card = NoteCard()
        if card.isVisible():
            card.hide()
        else:
            card.open()

    return toggle
