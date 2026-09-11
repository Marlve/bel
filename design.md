# Build prompt — PySide6 radial overlay

Copy everything below the line into Claude Code.

---

Build a Windows desktop overlay in **Python 3.11 + PySide6**: a hotkey-summoned donut pie menu whose four wedges open small always-on-top panels. It is a background app — no main window, no taskbar entry, tray icon only.

## Architecture

Four separate top-level widgets, none parented to each other:

| Widget | Role | Lifetime |
|---|---|---|
| `RingOverlay` | full-screen frameless overlay, custom-painted donut menu | shown per hotkey press |
| `PromptBar` | single-line input, launched from the left wedge | closes on send/Escape |
| `ResultCard` | 340×340 square holding a Claude response | outlives the overlay, user dismisses |
| `NoteCard` / `TodoCard` | 340×340 persistent squares | persist across sessions |

Every panel is `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool` with `Qt.WA_TranslucentBackground`. `Qt.Tool` keeps them out of the taskbar. `ResultCard` must **not** be a child of `RingOverlay` — it survives the overlay closing, and the corner flight is an animation on its own window geometry.

Global hotkey: `Ctrl+Space`. Use a Windows `RegisterHotKey` binding via `ctypes` with a `QAbstractNativeEventFilter`; do not poll.

## Geometry — the ring

Everything is a ratio of the outer radius **R = 168 px** at 1.0 scale. Recompute on DPI change.

- Inner radius `0.35R` (59 px) — the donut hole
- Icon centroid at `0.68R` from centre; icon box 24×24, 2 px stroke
- Wedge gap: **3° of arc**, split evenly both sides of each boundary
- Corner radius 4 px on all four wedge corners
- First wedge centred at **−90°** (straight up), winding clockwise
- Widget size `2·(R + pop + blur)` square, 400 px
- Dead zone: `r < 0.35R` or `r > 1.9R` → cancel

Four wedges, 90° each:

| Index | Direction | Action |
|---|---|---|
| 0 | up | Todo square |
| 1 | right | Sticky note |
| 2 | down | *unassigned — leave a stub* |
| 3 | left | Ask Claude |

**Hit testing is polar, never path-based:**

```python
idx = int(((degrees(atan2(dy, dx)) + 90 + arc/2) % 360) // arc)
```

Ignore the wedge gaps when testing so there are no dead lines between items, and ignore the hover pop offset so the target never moves under the cursor. Hit sectors run from the hole out to `1.3R`.

## Colours

```
wedge idle      #171B24    icon idle        #B4BDD0
wedge border    #242C3A    icon on hover    #0B0C10
wedge hover     #8AB4FF    scrim            #000 @ 55%
wedge pressed   #6E97E3    hover glow       #8AB4FF @ 22%, 18px
card surface    #141924    card border      #2A3243
note surface    #1C1A14    note border      #3A3520    note accent #E8C547
```

All fills are opaque. Only the backdrop scrim uses alpha.

## Animation

Drive every hover property from **one 0→1 float per wedge** so a wedge caught mid-retreat animates from where it actually is. Use `QVariantAnimation` / `QPropertyAnimation`; repaint only dirty wedge rects.

**Open (430 ms).** Ring scales 0.30 → 1.00, `OutBack` overshoot 1.56. Opacity 0 → 1 over the first 170 ms, `OutCubic` — faster than the scale, so it reads as arriving rather than fading. Wedges stagger 26 ms apart clockwise from index 0. Scrim fades to 55% over 220 ms, linear, never bounces. Origin is the **cursor**, not the screen centre.

**Hover (140 ms in / 110 ms out).** The hovered wedge translates `0.07R` (12 px) outward along its own bisector and grows its outer radius R → 1.035R; icon rides the wedge and scales 1.0 → 1.08. `OutBack` 1.15 in, `OutCubic` out. Neighbours do not move — no ripple.

**Select (400 ms).** Chosen wedge pushes to `0.15R`, scales 1.06, fill steps one stop brighter. All others drop to 12% opacity and 0.88 scale over 120 ms. The picked wedge is alone on screen for ~150 ms before anything closes.

**Close (150 ms).** Whole ring to 0.30 scale, fade out, `InQuad`. No stagger, no bounce. Fire the action signal at the **start** of the close, not the end.

Honour the system reduced-motion setting by setting all durations to zero.

## The prompt bar (left wedge)

The wedge does **not** morph into a text box — Qt cannot meaningfully interpolate an annular sector into a pill. It hands off:

1. **Ring exit, 130 ms** — other wedges collapse; the Claude wedge holds its hover pose 60 ms first so the click registers.
2. **Rect grow, 280 ms `OutCubic`** — one rounded rect animates from the wedge bounding box (96×96 at 0.68R) to the final field (520×56, fully round). Starts −0.32R left of centre, ends centred. The wedge cross-fades out over the first 110 ms.
3. **Field arrives, 90 ms** — only once the rect is at rest: place the real `QLineEdit`, fade in placeholder/caret/hint, then take focus. **Never animate a widget that contains text**, and never take focus mid-flight or the IME candidate window opens against a moving target.

Icon continuity carries the illusion: the 24 px mark travels from the wedge centroid to 26 px from the field's left cap on the same curve as the rect, unchanged in size.

Text inset 58 px left / 44 px right. Line height 22 px, ceiling 3 lines, then scroll. Enter sends, Shift+Enter newlines and grows the box in 22 px steps, Escape steps **back to the ring** (not straight to hidden). While the ring is up, a printable keypress jumps straight into the prompt.

Field states: empty (placeholder, inert hint), typing (hint lights on non-whitespace, border warms one step), sending (read-only, text dims, accent border), rejected (border `#8A5A5A`, shift 4 px twice over 90 ms, text preserved).

## The result card

Born as the prompt bar's **exact rectangle at its exact position** the frame the prompt bar disappears — same rect, no cross-fade between two objects.

- Flight 420 ms `OutCubic`, **no overshoot** (overshoot near a screen corner reads as an error)
- Corner radius 999 → 12 px over 300 ms, on the same curve
- Docks to **340×340 px, 24 px from the work-area edges**, top-right, on the monitor holding the cursor. Work area, not monitor bounds, so it never hides under the taskbar.
- Scrim clears in parallel and finishes first — the desktop is interactive before the card lands
- Content streams only **after** geometry is at rest; lines fade in on arrival, 200 ms each; caret at the end of the last line, gone on completion
- Fixed frame with internal scroll — the square never grows to fit. Top/bottom fades when scrollable.
- Not stackable: only one card is ever live (one wedge can hold a Claude session at a time); a second prompt for the same wedge reveals the existing card instead of opening another. Earlier drafts of this doc described push-down stacking up to 3 cards - that was removed from the code and is no longer the design.
- No auto-hide. Dismiss slides 24 px right and fades over 140 ms — exits toward the edge it rested against.
- Padding 18 px; header = 14 px mark + label + close; prompt echo 1 line elided at 11 px; body 13/20 px
- Shadow `0 22 54 rgba(0,0,0,.55)`

## Todo square (wedge 0)

340×340, launched from the wedge with the same born-at-the-wedge geometry animation, **380 ms** (shorter — it travels less). Radius 999 → 10 px.

- Padding 16 px vertical / 14 px sides; row height **36 px**, full width; 6 rows visible then scroll
- Checkbox 17 px, 4 px radius, 1.5 px stroke; label 14.5 px, elided at one line
- Ticked row: 40% opacity + strikethrough, **stays in place** — nothing reorders under the cursor
- The whole square is the grab handle (no title bar). Press and move **more than 4 px** and it drags; under 4 px on a row it ticks.
- Snap to a 24 px screen-edge margin when released within 16 px of one
- The wedge is a **toggle**, not a spawn: if already open it raises and flashes the border; if closed it reopens at its last saved position, not a default corner. Hence no close control on the face.

## Sticky note (wedge 1)

Identical footprint, launch and drag; amber instead of blue.

- Surface `#1C1A14`, border `#3A3520`, accent `#E8C547`; header strip = 9 px mark + `NOTE` in 10 px mono
- Body 15/22 px, `#F0EADA`, padding 14 px
- **Drag surface shrinks to the header strip and the 14 px margins** — dragging cannot fight text selection. Press inside the text and you edit; press the margin and you move.
- Focus: caret to end of existing text, 560 ms after launch (after the geometry settles)
- Autosave on a 400 ms idle timer and on hide. No save control, no dirty indicator.
- Text past the frame scrolls; the square never grows. If longer notes are needed, add a corner resize grip — not auto-height.
- Modifier + pick opens a *new* note offset 24 px down-right; a plain pick focuses the most recent

## What to animate, and what to avoid

| Property | Mechanism | Verdict |
|---|---|---|
| Rectangle geometry | `QPropertyAnimation` | Exact and cheap. Carries the entire morph. |
| Opacity | `QGraphicsOpacityEffect` | Fine for cross-fades, but forces an offscreen pixmap — use on the small prompt frame, never the whole overlay. |
| Wedge fill/stroke | `QVariantAnimation<QColor>` | Per-channel, repaint only. Safe on all four at once. |
| Wedge shape → rounded rect | path interpolation | **Avoid.** `QPainterPath` has no meaningful interpolation between an annular sector and a pill. |
| Font size / text metrics | — | **Avoid.** Reflows and re-hints every frame. Place text only at rest. |
| Blur behind overlay | platform composition | Optional and expensive on Windows. A flat 55% scrim reads the same. |
| Whole overlay window | `windowOpacity` | Final fade-out only. Using it during the morph washes out the cross-fade. |

## Paint order

Scrim → all idle wedges → hovered wedge last (so its glow sits above neighbours) → icons per wedge in the same transform as their wedge. Antialiasing on. Cache each wedge `QPainterPath`; rebuild only when the slice count or R changes.

## Accessibility

Icons alone are ambiguous: expose each wedge's name via `QAccessible`, and show a tooltip after 600 ms of dwell. Escape cancels, Enter commits the hovered wedge, arrow keys move the selection. Respect reduced motion.

## Deliverables

Separate modules — `ring_overlay.py`, `prompt_bar.py`, `result_card.py`, `note_card.py`, `todo_card.py`, `hotkey.py`, `theme.py` (every colour and duration above as named constants, nothing hard-coded at a call site), `app.py`. Wedge actions dispatch through a signal so adding wedge 2 later is a registration, not a rewrite. Wire the Claude call behind an interface with a stub implementation.
