# render() turns a Claude turn's raw streamed text into the rich text
# ChatCard's QLabel (Qt.RichText) shows. It's called on the *whole*
# accumulated turn on every chunk (see claudeChatCard.onChunk()), not
# incrementally - so there's no streaming state to track here: a marker
# that hasn't been closed yet (e.g. a lone "**") simply doesn't match any
# regex below and is left as literal escaped text, resolving itself once
# the closing marker streams in.

import html
import re

from style import CHAT_MONO_FAMILY

_FENCE_RE = re.compile(r"```[^\n`]*\n(.*?)\n```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_BOLD_RE = re.compile(r"\*\*(\S(?:.*?\S)?)\*\*")
_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*(\S(?:.*?\S)?)\*(?!\*)")
_ITALIC_UNDERSCORE_RE = re.compile(r"(?<![\w_])_(\S(?:.*?\S)?)_(?![\w_])")
_BULLET_RE = re.compile(r"^-\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\d+\.\s+(.*)$")

_FENCE_TOKEN = "\x00%d\x00"
_FENCE_TOKEN_RE = re.compile(r"^\x00(\d+)\x00$")
_CODE_TOKEN = "\x01%d\x01"


def render(text):
    """raw Claude turn text -> safe Qt rich text. html.escape() runs first,
    always, so nothing in `text` can inject real markup - everything added
    after that point is a tag this module put there itself."""
    escaped = html.escape(text)

    fences = []

    def stash_fence(match):
        fences.append(f'<pre style="font-family:{CHAT_MONO_FAMILY};">{match.group(1)}</pre>')
        return _FENCE_TOKEN % (len(fences) - 1)

    body = _FENCE_RE.sub(stash_fence, escaped)
    lines = [_render_line(line) for line in body.split("\n")]
    body = "\n".join(_wrap_lists(lines))

    for index, fence in enumerate(fences):
        body = body.replace(_FENCE_TOKEN % index, fence)
    return body


def _render_line(line):
    if _FENCE_TOKEN_RE.match(line):
        return ("raw", line)
    bullet = _BULLET_RE.match(line)
    if bullet:
        return ("list", False, _inline(bullet.group(1)))
    numbered = _NUMBERED_RE.match(line)
    if numbered:
        return ("list", True, _inline(numbered.group(1)))
    return ("raw", _inline(line))


def _wrap_lists(rendered_lines):
    out = []
    group = []

    def flush():
        if not group:
            return
        tag = "ol" if group[0][1] else "ul"
        items = "".join(f"<li>{content}</li>" for _, _, content in group)
        out.append(f"<{tag}>{items}</{tag}>")
        group.clear()

    for item in rendered_lines:
        if item[0] == "list":
            if group and group[0][1] != item[1]:
                flush()  # a bullet/numbered switch with no blank line starts a new list
            group.append(item)
            continue
        flush()
        out.append(item[1])
    flush()
    return out


def _inline(text):
    spans = []

    def stash_code(match):
        spans.append(f'<code style="font-family:{CHAT_MONO_FAMILY};">{match.group(1)}</code>')
        return _CODE_TOKEN % (len(spans) - 1)

    text = _INLINE_CODE_RE.sub(stash_code, text)
    text = _BOLD_RE.sub(r"<b>\1</b>", text)
    text = _ITALIC_STAR_RE.sub(r"<i>\1</i>", text)
    text = _ITALIC_UNDERSCORE_RE.sub(r"<i>\1</i>", text)

    for index, span in enumerate(spans):
        text = text.replace(_CODE_TOKEN % index, span)
    return text
