# Tab completion for `! ` commands, shared by the chat composer and the
# prompt bar. No Qt here; commandInput.py wires it into the fields.

import os

import timetable

COMMANDS = (*timetable.COMMANDS, "save", "ss", "read", "new", "help")


def typed_command(text):
    """What follows the "!" in `text`, or None if `text` isn't a command being typed."""
    if not text.startswith("!"):
        return None
    return text[1:].strip().casefold()


def lead(text):
    """The "!" and whatever spaces follow it, kept as typed so a completion extends the text."""
    return text[:len(text) - len(text[1:].lstrip())]


class CommandCompleter:
    """Tab fills the longest start the matching commands share. With nothing
    left to fill, further Tabs cycle through the matches."""

    def __init__(self):
        self.matches = []
        self.index = 0
        self.filled = None  # the text this last wrote; if the field still holds it, Tab continues the cycle

    def step(self, text):
        """(matches, index, completed text) for a Tab pressed on `text`, or
        None when `text` isn't a command start. Changes nothing."""
        if text == self.filled:
            index = (self.index + 1) % len(self.matches)
            return self.matches, index, lead(text) + self.matches[index]
        typed = typed_command(text)
        matches = [command for command in COMMANDS if typed is not None and command.startswith(typed)]
        if not matches:
            return None
        shared = os.path.commonprefix(matches)
        if len(shared) > len(typed):
            return matches, -1, lead(text) + shared  # the next Tab starts the cycle at the first match
        return matches, 0, lead(text) + matches[0]

    def complete(self, text):
        """The text after a Tab, or None when `text` isn't a command start (Tab then does its normal job)."""
        stepped = self.step(text)
        if stepped is None:
            return None
        self.matches, self.index, self.filled = stepped
        return self.filled

    def ghost(self, text):
        """What Tab would add after `text`, to show dimmed - "" when it adds nothing."""
        stepped = self.step(text)
        if stepped is None or not stepped[2].casefold().startswith(text.casefold()):
            return ""
        return stepped[2][len(text):]
