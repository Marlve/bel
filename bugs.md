# Bugs

Postmortems for bugs worth remembering, so we don't repeat the mistake.

## Tilt vanishes instantly instead of animating back to 0 (chat_card.py)

**Symptom:** Tab icon tilts in fine on hover-in, but the instant the cursor
leaves the arm zone and the dock state drops out of TAB, the tilt disappears
immediately instead of easing back to 0 - even though `tilt_tween` really is
still running and `self.tilt` really is still ticking down toward 0.

**Root cause:** `paintEvent()` only applied the rotation (`painter.rotate
(self.tilt)`, drawn against the small `puckRect()`) inside `if
self.isTabbed():`, i.e. gated on `dock.state == TAB`, not on `self.tilt`
itself. The moment state left TAB, painting fell straight to the plain,
unrotated full-rect branch - so `tilt_tween` kept animating `self.tilt` in
the background, calling `update()` every tick, but nothing was ever drawn
using that value again. A live in-flight animation with no visual effect
looks identical to an instant snap.

**Fix:** changed the paint gate to `if self.isTabbed() or self.tilt !=
0.0:` so the rotated puck keeps being drawn - shrinking/untilting through
`puckRect()`'s existing width-based scaling - for as long as there's real
tilt left to render, regardless of which state the dock has already moved
to.

**Regression this caused:** that gate was too broad - `self.tilt != 0.0`
stays true for a few hundred ms on *any* transition out of TAB, including
TAB -> OPEN (clicking the tab to reopen the real chat). During that
transition the window is growing to full size, but `puckRect()` clamps to
a fixed tiny square once width passes `TAB_WIDTH`, so paint kept drawing
that stuck tiny puck instead of the growing full-card frame, until the
tilt tween hit exactly `0.0` - then it snapped straight to full size. Fixed
by also checking the dock state: `self.isTabbed() or (self.tilt != 0.0 and
dock_state != OPEN)` - the lingering rotated-puck paint only applies when
heading toward a still-small state (HIDDEN), not when reopening.

**Lesson (updated):** the fix above wasn't wrong, just incomplete - fixing
"painting keyed off state truncates an in-flight animation" by keying
purely off the animated value swaps one blind spot for another, because
different destination states want different paint treatments for the same
mid-flight tilt value (shrink-and-fade vs. grow-to-full). When a paint
branch needs to outlive its triggering state, gate it on *both* the
property's value and which state is actually being transitioned to -
not the value alone.

**Lesson (original):** when a visual property (tilt, opacity, offset...) is animated
independently of the state machine that triggered it, painting must key off
the *property's current value*, not off the state. Gating a paint branch on
state alone silently truncates any animation whose tail hangs past the
state transition - the tween looks broken even though it's numerically
correct, because "correct value, never painted" is indistinguishable from
"reset to 0".

**How it was found:** the earlier fix below (blockSignals on `Tween.run()`)
addressed a real but different glitch - it did not fix this symptom, per
direct user report after testing. Traced it by re-reading `paintEvent()`
and noticing the rotation branch's condition didn't reference `self.tilt`
at all.

## Tween twitch on retarget (anims/clock.py)

**Symptom:** Retargeting a running/finished `Tween` mid-flight (e.g. the tab
icon's tilt resetting when the cursor left the screen, or the dock's
hidden/tab geometry animation) caused a visible instant twitch: the property
snapped to the *new* end value, then snapped back to the *new* start value,
then finally animated smoothly between them.

**Root cause:** `QVariantAnimation.stop()` does not reset `currentTime` to 0
- it leaves it wherever the previous run ended (typically at the old
duration, i.e. progress = 1.0). `Tween.run()` called `setStartValue()` /
`setEndValue()` right after `stop()`, and Qt recomputes `currentValue` (and
emits `valueChanged`) immediately whenever start/end changes while stopped.
So the stale progress=1.0 got applied against the *new* end value first
(jump to target), and then `start()` reset `currentTime` to 0 and recomputed
against the *new* start value (snap back) - two spurious ticks before the
real eased animation began.

**Fix:** `blockSignals(True)` around the `setStartValue`/`setEndValue`/
`setDuration`/`setEasingCurve` calls in `Tween.run()`, unblocking right
before `start()`. Only the genuine animated ticks reach `on_tick` now.

**Lesson:** `stop()` on a `QVariantAnimation` is not a clean reset - any
property set on a stopped-but-not-fresh animation can synchronously fire
`valueChanged` against leftover state from the previous run. When
reconfiguring a QVariantAnimation/QPropertyAnimation to retarget it
mid-flight, block signals (or otherwise suppress ticks) while changing its
start/end/duration, and only let it emit once `start()` is actually called.

**How it was found:** added `print()` on every tick/state-change (see
`EdgeDockDriver._apply` in `src/edge_dock.py`, `onTiltTick`/
`onDockStateChanged` in `src/chat_card.py`, and the off-trigger branch in
`src/edge_trigger.py::checkCursor`) and read the sequence of printed values
around the transition - the "end value, then start value, then real ramp"
pattern gave away the stale-currentTime cause immediately.

## Alt+Tab away from the open ring left it stuck, Escape dead (pieMenu.py)

**Symptom:** Open the ring, Alt+Tab to another window, and the ring stays
floating on top, unresponsive - Escape no longer closes it. The ring forces
itself into OS foreground on open (`util.force_foreground`, since a
background hotkey-listener thread can't call `SetForegroundWindow`
directly), but nothing handled the reverse: losing that foreground again.

**First fix attempt (wrong):** added a `changeEvent()` override that closed
the ring on `QEvent.WindowDeactivate`. It compiled, and a test calling
`changeEvent()` directly with a synthetic `QEvent(QEvent.WindowDeactivate)`
passed - but did nothing in the real app.

**Root cause:** `PieMenu` is `Qt.FramelessWindowHint | WindowStaysOnTopHint
| Qt.Tool`. For this combination, Qt/Windows never actually delivers the
discrete `QEvent.WindowActivate`/`WindowDeactivate` events - only the
generic `QEvent.ActivationChange`, which fires for *both* gaining and
losing focus. `isActiveWindow()` is what tells you which direction it went.
The `WindowDeactivate` check was watching for an event type that never
occurred, so the guard always short-circuited before `beginClose()` could
run - a silent no-op, not a crash. The test didn't catch this because it
called `changeEvent()` directly with a hand-built event, bypassing the real
Qt/Windows activation plumbing the live app depends on.

**Fix:** listen for `QEvent.ActivationChange` instead, and use
`self.isActiveWindow()` after `super().changeEvent(event)` to act only on
the losing-focus direction.

**Lesson:** a window's actual `QEvent` traffic depends on its flag
combination (frameless/tool/topmost/translucent windows are the ones most
likely to skip the "obvious" discrete event) - don't assume the
documented/expected event fires for a given window without confirming it.
A test that calls an event handler directly with a hand-built `QEvent`
proves the handler's *logic* is correct, but proves nothing about whether
the app ever actually receives that event type - that only shows up
running the real thing.

**How it was found:** added a `print()` in `changeEvent()` logging every
`event.type()` plus `isActiveWindow()`, ran the real app, and had the user
reproduce it live (open the ring, Alt+Tab) while watching the log. The
printed sequence showed only `type=99` (`ActivationChange`) toggling
`isActiveWindow` True/False - `WindowDeactivate` (`type=25`) never once
appeared.
