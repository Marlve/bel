# Calendar nudge card — bel

A proactive card that appears at the screen edge to surface upcoming calendar/assignment items, with a close ("✕") button as its only action.

## Behaviour

1. **Quiet** — a 5px rail at the screen edge (same rail the chat card retreats to). Nothing visible.
2. **Nudge** — the card slides out (240ms, decelerating curve). One sentence + a source line (e.g. "from calendar · 2 items"). Auto-retires after 12s if untouched — that counts as ignored.
3. **Expand** — hovering reveals the actual items (name + due time), no header icon, no actions beyond the close button.
4. **Gone** — the close button collapses it back to the rail, sliding with the same 240ms decelerating motion as the entrance, reversed. Snoozed and ignored both end here; the resting state is always the same.

## What was removed

- The Pip mark/icon from the collapsed card header — no logo.
- All three action buttons (Add / Later / Ask) from the expanded state.
- The "acted" confirmation state ("Both added to your to-do list") and its step — there is no accept flow right now, the card is display-only.

## Tone control

Three registers for the same underlying data, switchable independently of the flow steps:
- **Casual** — "hey — two things due before Friday. want them in your list?"
- **Plain** — "Two assignments are due before Friday."
- **Terse** — "2 due · by Fri"

## Style

Matches the bel neutral palette: `#141416` card, `#2D2E31` border, `#86878B`/`#6E6F73` secondary text, Geist Mono for the source line and tone labels. No accent colour in this card currently.

## Open question

This card currently has no way to act on a nudge — it's a pure notice. If/when an accept flow returns, decide then whether it lives here or only in the chat card's own reply shapes.
