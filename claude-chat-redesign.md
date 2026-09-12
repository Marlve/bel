# Chat card — bel

Matches the todo/notes shell: 340px wide, `#141416` body (surface 100), `#191A1C` header (150), 9px radius, `#2D2E31` 1px border, same bottom-right resize grip (20px hit zone, 14px paint, 2 strokes not 3, `#4A4B4F` rest → `#86878B` hover → `#E8E8EA` drag).

**Placeholder mark:** the small triangle icon in the header stands in for bel's real logo/app icon. It is not a final asset — swap it out, don't treat its shape or glow as spec.

## Header

Title "Claude", left-aligned. Then minimize (`–`, Geist Mono, `#86878B` → `#E8E8EA` hover) and close (`✕`, same treatment) immediately to its right — same two controls, same order, as the todo and notes cards. No turn counter or other metadata in the header.

## Body: five reply shapes, no buttons

Most replies are **plain prose** — no bubble, no border, no inset. That's the default and should look intentional, not like a block failed to load.

The question is right-aligned in a `#1D1E21` bubble (`8px 8px 2px 8px` radius — the one place rounding does real work, marking the sender). The answer sits directly on the card surface below it.

Four reply shapes get a bordered inset (`#17181A` fill, `#232427` border, 7px radius) when the answer contains something actionable:

- **Dated items** — a list of task rows with a coloured status dot (see accent note below) and nothing else. Read-only.
- **Time blocks** — a day's proposed schedule, rows with a time label and a bar scaled to duration.
- **Weighed options** — two considerations side by side with a vertical rail, one optionally marked as the lean.
- **Note preview** — the note exactly as it will look on the sticky card, shown on its own surface.

**No buttons anywhere in the card right now** — no accept/edit/show-me actions. This was deliberately stripped; add them back only when there's a real destination to hand off to.

*(A sixth shape, "screen reference" — pointing at what's on screen with a named region chip — was designed but removed for now. Reintroduce if/when that feature is built.)*

## Footer

Plain input row, `#121213` background, `#202123` top border. Placeholder "ask anything" at `#5C5D61`, blinking caret (`#D8D9DC`, 5×13px). A context chip (e.g. "reading Chrome") can appear above the input row when Claude is anchored to something specific.

## Colour

**One accent only: sand (`#C2A878`).** It marks the nearest deadline in a dated-items list and the one fixed block in a time-block plan — that's it. Clay and slate exist in the palette but are held in reserve; don't deploy them just because they're defined. Everything else is a brightness step, not a colour.

## Shared rules

- Prose gets no container; a bordered inset is earned only by an object, never used for decoration.
- One accent working at a time beats three accents competing for attention.
- Hover changes one property at a time.
