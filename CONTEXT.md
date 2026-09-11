# Bel

A Windows overlay app: a radial pie menu opens on a hotkey, its wedges launch
small always-on-top cards (todo, note, Claude chat, settings).

## Language

**State**:
The finite, named mode a widget is in at a point in time, with named
transitions between values (e.g. the pie menu's `HIDDEN/OPENING/OPEN/...`,
the chat card's edge-dock `OPEN/COMPACT/HIDDEN/TAB`, the prompt bar's
`EMPTY/TYPING/SENDING/REJECTED`). Every stateful widget uses this one word.
_Avoid_: Phase, mode - both were used for this same concept before being
standardized on "state".

**View**:
A widget's Qt-facing half: the widget children it owns, its layout, and its
paint/input event handlers. Owns nothing that ticks on its own.

**Animation**:
A widget's Qt-facing half that owns every `Clock`/`Tween`/`QTimer` it drives,
plus the tick/done callbacks that write into that widget's State. Never
painted directly - it feeds values the View reads.
