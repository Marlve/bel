# Build prompt — Claude chat card with edge dock

Copy everything below the line into Claude Code.

---

Build the **Claude chat overlay** for a Windows desktop app in **Python 3.11 + PySide6**. It is one flow: a radial menu wedge opens a prompt bar, the prompt bar becomes a small chat card docked in a screen corner, and that card hides itself off the screen edge and comes back on approach.

Scope: only this flow. Assume a `RingOverlay` widget already exists and emits `wedge_picked(index)`; wire to index 3 (the left wedge).

## Windows

Three separate top-level widgets. None is a child of another.

| Widget | Role | Lifetime |
|---|---|---|
| `PromptBar` | single-line input, born from the wedge | closes on send or Escape |
| `ChatCard` | 340×340 square, transcript + composer | outlives the overlay; user dismisses |
| `EdgeTrigger` | invisible proximity strip on the right edge | lives with the ChatCard |

All are `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool` with `Qt.WA_TranslucentBackground`. `Qt.Tool` keeps them out of the taskbar.

`ChatCard` must **not** be parented to the ring overlay — it survives the overlay closing, and every dock move is an animation on its own window geometry.

## Colours and type

```
card surface     #17181A    card border (open)     #2D2E31
composer field   #1B1C1F    card border (tab out)  #4C4D52
accent           #D8D9DC    user bubble            #24252A
body text        #E8E8EA    claude turn text       #C8C9CD
label mono       #86878B    inert hint             #3C3D41
```

Body and messages 12.5 px / 18 px. Header label 9.5 px mono, 0.14em tracking. Shadow `0 22 54 rgba(0,0,0,.55)` on every state.

Keep all of this in a `theme.py` as named constants. Nothing hard-coded at a call site.

## Step 1 — wedge to prompt bar

The wedge does **not** morph into a text field. Qt cannot meaningfully interpolate an annular sector into a pill, so it hands off:

1. **Ring exit, 130 ms** — the other wedges drop to 12% opacity and 0.88 scale. The Claude wedge holds its hover pose for 60 ms first, so the click registers before anything leaves.
2. **Rect grow, 280 ms `OutCubic`** — one rounded rect animates from the wedge bounding box (96×96 px at 0.68R) to the final field, **520 × 56 px, fully round**. It starts left of centre and lands centred. The wedge cross-fades out over the first 110 ms.
3. **Field arrives, 90 ms** — only once the rect is at rest: place the real `QLineEdit`, fade in placeholder and hint, *then* take focus.

**Never animate a widget that contains text**, and never take focus mid-flight — the IME candidate window will open against a moving target.

The 24 px accent mark is the visual thread: it travels from the wedge centroid to 26 px from the field's left cap on the same curve as the rect, unchanged in size.

Field: text inset 58 px left / 44 px right, `↵` hint on the right that lights accent on non-whitespace content. Enter sends, Escape returns to the ring (not straight to hidden).

## Step 2 — prompt bar to chat card

The card is **born as the prompt bar's exact rectangle at its exact position**, the frame the prompt bar disappears. Same rect, no cross-fade between two objects.

- Flight **420 ms `OutCubic`, no overshoot** — overshoot near a screen corner reads as an error
- Corner radius 999 → 10 px over 300 ms on the same curve
- Docks to **340 × 340 px, 24 px from the work-area edges**, top-right, on the monitor holding the cursor. Work area, not monitor bounds, so it never slides under the taskbar.
- The ring's scrim clears in parallel and finishes first — the desktop is interactive before the card lands
- Content fades in only **after** geometry is at rest

## Step 3 — the card is a chat

340 × 340 fixed, 14 px padding, three rows:

**Header (flex none).** 13 px accent mark, `CLAUDE` in 9.5 px mono, close `✕` on the right.

**Transcript (flex 1, bottom-anchored).** Newest message sits just above the composer; older ones scroll off the top. User turns are right-aligned bubbles: `#24252A`, radius `9 9 3 9`, padding 7×9, max width 84%. Claude turns are plain left-aligned text, no bubble — one bubble style is enough to tell the two apart, and unbubbled answers read faster at 12.5 px.

Streaming appends text with a 5 px accent caret at the tail. Auto-scroll **only if the user is already at the bottom** — if they scrolled up to read, incoming text must not yank the view.

**Composer (flex none).** 32 px pill, `#1B1C1F`, 11 px horizontal padding, 1 px border that warms to `#3E3F44` on content. Present from the moment the card lands — no mode switch between reading and asking. Enter sends, Shift+Enter newlines, **Escape blurs the field rather than closing the card**.

The square never grows. A conversation has no length limit, so the transcript scrolls inside a fixed frame. If a longer view is wanted, add a control that reopens the same thread in a normal resizable window — the overlay stays predictable, the window handles the long tail.

## Step 4 — the edge dock

Four states, right edge of the work area.

| State | Geometry |
|---|---|
| `OPEN` | 340 × 340, 24 px from top and right edges |
| `COMPACT` | 64 × 64 puck, same corner, mark only |
| `HIDDEN` | the puck fully past the right edge — **nothing visible** |
| `TAB` | 26 px of the puck out, **rotated −9°**, hinged on its right edge |

**Leaving is two moves.** Compact first: the square shrinks in place to the 64 px puck over **300 ms `OutCubic`**, staying in its corner so it reads as folding away rather than fleeing. Then, **220 ms later**, the puck slides fully offscreen over 300 ms.

**Coming back.** Cursor within **180 px** of the right edge → the tab tilts out (300 ms slide, 260 ms rotation). Past **260 px** → it retracts. **A click on the tab opens it**; hover never does.

Hidden means *fully* hidden — no rail, no sliver. The cost is discoverability, which is exactly why the compact step exists: watching the square fold into a puck and slide out is what teaches the user where it went.

### Timers

- **6 s** idle before the compact step
- **2.5 s** after the cursor leaves an open card
- The timer **never runs** while a response is streaming, while the composer holds focus, or while the cursor is over the card. A card that hides itself mid-sentence is indistinguishable from a crash.
- Typed-but-unsent text survives a retreat and is still there on the next open.

### Hysteresis

The tab arms at 180 px and disarms at 260 px. Without that gap, a cursor resting near the boundary flickers the card on every pixel of hand tremor.

## Implementation constraints

**Proximity without a global hook.** Do not install a screen-wide mouse hook. Keep `EdgeTrigger` as a thin always-on-top window along the right edge — full work-area height, 180 px wide, click-through (`Qt.WA_TransparentForMouseEvents` off but painted fully transparent, or a `setMask` region), and read its enter/leave events. It costs nothing when the cursor is elsewhere and it dies with the app.

**One animation, four targets.** Keep a single `QPropertyAnimation` on the card's `geometry` and retarget it, restarting from the current position — that is what makes an interrupted retreat animate from where it actually is rather than snapping.

**The tilt cannot be a window rotation.** Windows will not rotate a window. Make the tab window slightly larger than the visible puck and rotate the *painted content* inside it with `QPainter.rotate()`, keeping the window rect axis-aligned. Hit-test against the rotated shape, not the window rect.

**Focus discipline.** Tilting out must never take focus — the user is reaching past the card, not for it. Opening by click must not steal focus into the composer either; only a click *in the composer* moves the caret. Otherwise a card that slides out mid-typing swallows the next keystroke.

**What not to animate.** Font size or text metrics (reflows and re-hints every frame — place text only at rest). `QPainterPath` interpolation between the wedge and the pill. `windowOpacity` during the morph, which washes out the cross-fade; use it for the final fade-out only. `QGraphicsOpacityEffect` is fine on the small prompt frame but forces an offscreen pixmap — never apply it to the whole overlay.

## Dismissal and stacking

No auto-close on something the user asked for and may still be reading. Dismiss via the `✕`, or Escape while the card holds focus. On dismiss it slides 24 px right and fades over 140 ms, exiting toward the edge it rested against.

A second prompt while a card is open pushes the existing card **down 352 px** (340 + 12) rather than replacing it, up to three cards; past that the oldest closes.

## Deliverables

`prompt_bar.py`, `chat_card.py`, `edge_dock.py` (the four-state machine and its timers, testable without a GUI), `edge_trigger.py`, `theme.py`, and a `claude_client.py` interface with a stub that streams canned text word by word at 70 ms intervals so the UI can be driven without a live API.

Every duration, threshold and colour above belongs in `theme.py`.
