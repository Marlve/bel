# The three tone registers calendar-nudge.md defines for the nudge card's
# one-sentence summary - "switchable independently of the flow steps", so
# each is a pure function of (count, before) rather than tied to any one
# card state. TONE below is the one currently wired into the card; pointing
# it at a different function is the whole "switch".

_ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def _count_word(count):
    return _ONES[count] if count < len(_ONES) else str(count)


def casual(count, before):
    subject = "one thing" if count == 1 else f"{_count_word(count)} things"
    return f"hey — {subject} due before {before}. want them in your list?"


def plain(count, before):
    subject = "One assignment is" if count == 1 else f"{_count_word(count).capitalize()} assignments are"
    return f"{subject} due before {before}."


def terse(count, before):
    return f"{count} due · by {before}"


TONE = plain  # the neutral register - no accept flow exists, so avoid casual's implied question


def sentence(count, before):
    return TONE(count, before)


def source_line(count):
    return f"from calendar · {count} item" + ("" if count == 1 else "s")
