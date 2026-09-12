# Todo card & Notes card — bel

Both match the chat card's shell exactly: 9px radius, `#2D2E31` 1px border, same header bar, same bottom-right resize grip (20px hit zone, 14px paint, `#4A4B4F` rest → `#86878B` hover → `#E8E8EA` drag). They read as one widget family; only the body and footer differ.

## Todo card

- Width 340px. Body `#141416` (surface 100), header `#191A1C` (150) — same as chat.
- Header: title "Today" left-aligned, open-count on the right (`N OPEN`, Geist Mono 9px, `#86878B`), close `✕` at far right. No icon beside the title.
- Rows: checkbox (16×16, 4px radius, `#3B3C40` border / transparent fill at rest, `#D8D9DC` fill with a dark check glyph when done), task text (12.5px, `#E4E5E7`, strikethrough + `#5C5D61` when done), row background `#191A1C` on hover only.
- No dates on rows, no colour coding, no collapsed "later this week" group. Every open item is visible, full stop — an overlay todo list dies the day it becomes a backlog, and grouping/dating implied more structure than this card should carry.
- Footer: plain composer row, `#121213` background, top border `#202123`. Placeholder text "add a task" at `#5C5D61`, blinking caret (`#D8D9DC`, 5×13px). No leading icon — typing here appends a line, nothing else.

## Notes card

- Width 300px. Body `#1D1E21` (surface 200 — one step lighter than every other card; this is the one deliberate exception in the palette, since a note is a different kind of object).
- Header: title "Notes", close `✕`, same bar styling and position as the todo/chat header (`#232427` bottom border here since the surface is lighter). No icon.
- Body: plain text, 12.5px, `#E4E5E7`, 1.65 line height, no bubble or inset — click straight into the text to edit.
- Footer: stack navigation only, not a composer. Right-aligned page indicator (`N OF M`, Geist Mono 9px, `#5C5D61`), top border `#232427`. No colour tags, no dots — a note is edited in place, never composed from a bar below it.

## Shared rules carried from the rest of the system

- Brightness is the only emphasis channel; no accent colour on either card.
- Resize grip: 2 diagonal strokes (not 3), round caps, inset 5px from the corner, never touching the border radius.
- Hover changes one property at a time (row background, or border on the grip) — never surface + border + text together.
/
