# Same toggle shape as the todo/note wedges. Reads an "on_change" callback
# off this wedge's own config entry - pieMenu.py stashes its rebuild
# callback there before building - so this module and settingsCard.py never
# need to import pieMenu themselves.

from settingsCard import SettingsCard


def settings(config):
    on_change = config.get("on_change")
    card = None

    def toggle():
        nonlocal card
        if card is None:
            card = SettingsCard(on_change)
        if card.isVisible():
            card.hide()
        else:
            card.open()

    return toggle
