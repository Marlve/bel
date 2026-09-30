# render() turns a Claude turn's raw streamed text into the rich text
# ChatCard's QLabel (Qt.RichText) shows. It's called on the *whole*
# accumulated turn on every chunk (see claudeChatCard.onChunk()), not
# incrementally - so there's no streaming state to track here: a marker
# that hasn't been closed yet (e.g. a lone "**") simply doesn't match any
# regex below and is left as literal escaped text, resolving itself once
# the closing marker streams in.

import html
import re

import style

_FENCE_RE = re.compile(r"```[^\n`]*\n(.*?)\n```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_BOLD_RE = re.compile(r"\*\*(\S(?:.*?\S)?)\*\*")
_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*(\S(?:.*?\S)?)\*(?!\*)")
_ITALIC_UNDERSCORE_RE = re.compile(r"(?<![\w_])_(\S(?:.*?\S)?)_(?![\w_])")
_BULLET_RE = re.compile(r"^-\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\d+\.\s+(.*)$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_QUOTE_RE = re.compile(r"^&gt;\s?(.*)$")  # runs after html.escape()
_RULE_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")
_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")

_FENCE_TOKEN = "\x00%d\x00"
_FENCE_TOKEN_RE = re.compile(r"^\x00(\d+)\x00$")
_CODE_TOKEN = "\x01%d\x01"


def render(text):
    """raw Claude turn text -> safe Qt rich text. html.escape() runs first,
    always, so nothing in `text` can inject real markup - everything added
    after that point is a tag this module put there itself.

    A literal "\\n" between plain lines is this module's line-break - it
    relies on its caller rendering the result in a white-space:pre-wrap
    container (see claudeChatCard.setTurnHtml()), since Qt's rich text
    otherwise collapses a bare "\\n" to a space."""
    escaped = html.escape(text)

    fences = []

    def stash_fence(match):
        fences.append(
            f'<pre style="font-family:{style.CHAT_MONO_FAMILY}; background-color:{style.CHAT_CODE_BG};'
            f' color:{style.CHAT_BODY_TEXT};">{match.group(1)}</pre>'
        )
        return _FENCE_TOKEN % (len(fences) - 1)

    body = _FENCE_RE.sub(stash_fence, escaped)
    lines = [_render_line(line) for line in body.split("\n")]
    body = _join(_wrap_lists(lines))

    for index, fence in enumerate(fences):
        body = body.replace(_FENCE_TOKEN % index, fence)
    return body


def _join(pieces):
    # ClaudeChatCard's label renders this in a white-space:pre-wrap span, so
    # a bare "\n" here is a real line break within one paragraph. A blank
    # source line instead marks a paragraph break, wrapped in its own <p> so
    # the gap is a deliberate CHAT_PARAGRAPH_GAP margin rather than another
    # font-line-height "\n". A list/fence block already opens its own line,
    # so nothing is added directly next to one - only a blank line (pending)
    # still earns the next paragraph its gap.
    out = []
    paragraph = []
    pending_gap = False

    def flush_paragraph(with_gap):
        if not paragraph:
            return
        text = "\n".join(paragraph)
        if with_gap:
            text = f'<p style="margin:0;margin-top:{style.CHAT_PARAGRAPH_GAP}px;">{text}</p>'
        out.append(text)
        paragraph.clear()

    for is_block, text in pieces:
        if is_block:
            flush_paragraph(pending_gap)
            pending_gap = False
            out.append(text)
        elif text == "":
            flush_paragraph(pending_gap)
            pending_gap = True
        else:
            paragraph.append(text)
    flush_paragraph(pending_gap)
    return "".join(out)


def _render_line(line):
    if _FENCE_TOKEN_RE.match(line):
        return ("raw", line)
    if _RULE_RE.match(line):
        return ("block", f'<hr style="background-color:{style.CHAT_BORDER_TAB}; border-color:{style.CHAT_BORDER_TAB};">')
    heading = _HEADING_RE.match(line)
    if heading:
        # Sized from the (already scaled) body size, so it follows apply_scale().
        size = style.CHAT_BODY_SIZE * (1.2 if len(heading.group(1)) <= 2 else 1.0)
        return ("block", (
            f'<p style="margin:0;margin-top:{style.CHAT_PARAGRAPH_GAP}px;font-size:{size}px;">'
            f'<b>{_inline(heading.group(2))}</b></p>'
        ))
    quote = _QUOTE_RE.match(line)
    if quote:
        return ("block", (
            f'<p style="margin:0;color:{style.CHAT_LABEL_MONO};">'
            f'<span style="color:{style.CHAT_BORDER_TAB};">▎</span> {_inline(quote.group(1))}</p>'
        ))
    bullet = _BULLET_RE.match(line)
    if bullet:
        return ("list", False, _inline(bullet.group(1)))
    numbered = _NUMBERED_RE.match(line)
    if numbered:
        return ("list", True, _inline(numbered.group(1)))
    return ("raw", _inline(line))


def _wrap_lists(rendered_lines):
    """-> [(is_block, html), ...]. A list or fenced-code placeholder is a
    block (it opens its own line already); a plain line is not."""
    out = []
    group = []

    def flush():
        if not group:
            return
        tag = "ol" if group[0][1] else "ul"
        items = "".join(f"<li>{content}</li>" for _, _, content in group)
        out.append((True, f"<{tag}>{items}</{tag}>"))
        group.clear()

    for item in rendered_lines:
        if item[0] == "list":
            if group and group[0][1] != item[1]:
                flush()  # a bullet/numbered switch with no blank line starts a new list
            group.append(item)
            continue
        flush()
        text = item[1]
        if item[0] == "block":
            out.append((True, text))
            continue
        out.append((bool(_FENCE_TOKEN_RE.match(text)), text))
    flush()
    return out


def _inline(text):
    spans = []

    def stash_code(match):
        spans.append(f'<code style="font-family:{style.CHAT_MONO_FAMILY}; background-color:{style.CHAT_CODE_BG};">{match.group(1)}</code>')
        return _CODE_TOKEN % (len(spans) - 1)

    text = _INLINE_CODE_RE.sub(stash_code, text)

    def stash_link(match):
        spans.append(f'<a href="{match.group(2)}" style="color:{style.CHAT_ACCENT};">{match.group(1)}</a>')
        return _CODE_TOKEN % (len(spans) - 1)

    text = _LINK_RE.sub(stash_link, text)
    text = _BOLD_RE.sub(r"<b>\1</b>", text)
    text = _ITALIC_STAR_RE.sub(r"<i>\1</i>", text)
    text = _ITALIC_UNDERSCORE_RE.sub(r"<i>\1</i>", text)

    for index, span in enumerate(spans):
        text = text.replace(_CODE_TOKEN % index, span)
    return text
