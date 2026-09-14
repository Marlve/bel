# Centralized colors, sizes and motion for every overlay. Change a value here, not per-window.

# --- Shared neutral palette. One grayscale system - ring, prompt bar, and
# chat card all read from these same primitives, the way claude-chat-flow.md
# specified for the chat card alone. No hue anywhere; "accent" is near-white,
# not a color. ---

PALETTE = {
    "000": "#0D0D0E",
    "150": "#191A1C",
    "200": "#1D1E21",
    "250": "#232427",
    "300": "#2D2E31",
    "350": "#3B3C40",
    "375": "#3E3F44",
    "400": "#4A4B4F",
    "450": "#6E6F73",
    "500": "#86878B",
    "700": "#C9CACD",
    "750": "#D9D9DC",
    "800": "#E8E8EA",
}

SURFACE = PALETTE["150"]  # darkest surface: wedge idle fill, card header bar
SURFACE_RAISED = PALETTE["200"]  # one step up: prompt field, composer, notes card body
BORDER_DIM = PALETTE["300"]  # resting border, one step lighter than its surface
BORDER_WARM = PALETTE["375"]  # border once there's content/typing
BORDER_STRONG = PALETTE["400"]  # strongest border (tabbed-out dock state)
HINT = PALETTE["350"]  # inert icons/hints
MUTED = PALETTE["450"]  # placeholder text, dimmed secondary text
LABEL = PALETTE["500"]  # mono labels, muted body text
BODY_DIM = PALETTE["700"]  # secondary/idle text
BODY = PALETTE["800"]  # primary text
INK = PALETTE["000"]  # near-black, for text on top of the accent
ACCENT_NEUTRAL = PALETTE["750"]  # the one accent - near-white, not a hue

BACKGROUND = SURFACE + "dd"
TEXT = BODY
ACCENT = ACCENT_NEUTRAL
BORDER = BORDER_DIM

FONT_FAMILY = "Geist Mono"
FONT_SIZE = 11


# --- Shared spacing scale. Layout padding/spacing across the cards should
# step through these rather than reusing CHAT_PADDING for everything or
# typing a bare literal at the call site - see card-visual-polish/01. ---

SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16


# --- Pie menu ring. Sizes are ratios of RING_RADIUS so the ring scales as one. ---

RING_RADIUS = 152
RING_INNER = 0.35  # donut hole; the cursor inside it selects nothing
RING_HIT_OUTER = 1.3  # cursor past this selects nothing - a bit of slack past the ring's ink, not much
RING_LABEL = 0.68  # label centroid distance from the center

WEDGE_IDLE = SURFACE
WEDGE_BORDER = BORDER_DIM
WEDGE_HOVER = ACCENT
WEDGE_PRESSED = BODY_DIM
LABEL_IDLE = BODY_DIM
LABEL_HOVER = INK
SCRIM = "#000000"
SCRIM_ALPHA = 0.55
GLOW = ACCENT
GLOW_ALPHA = 0.14
GLOW_WIDTH = 8

# Open: ring pops out of the cursor, all wedges arriving together.
OPEN_MS = 345
OPEN_SCALE_FROM = 0.30
OPEN_EASING = "OutBack"
OPEN_OVERSHOOT = 1.56
OPEN_FADE_MS = 135  # opacity lands well before the scale does, so it reads as arriving
OPEN_FADE_EASING = "OutCubic"
SCRIM_MS = 220

# Hover: only the hovered wedge moves - it slides outward and grows a little.
HOVER_IN_MS = 110
HOVER_IN_EASING = "OutBack"
HOVER_IN_OVERSHOOT = 1.15
HOVER_OUT_MS = 90
HOVER_OUT_EASING = "OutCubic"
HOVER_PUSH = 0.07
HOVER_GROW = 1.035
LABEL_HOVER_SCALE = 1.08

# Select: the others drop away fast, the chosen wedge pushes out and holds alone before closing.
SELECT_OTHERS_MS = 95
SELECT_OTHERS_SCALE = 0.88
SELECT_OTHERS_ALPHA = 0.12
SELECT_HOLD_MS = 120
SELECT_PUSH = 0.15
SELECT_SCALE = 1.06
SELECT_EASING = "OutCubic"

# Close: whole ring shrinks back and fades, no bounce.
CLOSE_MS = 120
CLOSE_SCALE_TO = 0.30
CLOSE_EASING = "InQuad"


# --- Prompt bar. A wedge that needs typed input hands off to a text field
# instead of firing straight away, so the ring gets its own shorter exit and
# one rounded rect grows out of the wedge into the field. ---

RING_EXIT_MS = 105
RING_EXIT_HOLD_MS = 50  # chosen wedge holds its hover pose this long first, so the click registers
RING_EXIT_SCALE = 0.30
RING_EXIT_EASING = "InQuad"
GROW_MS = 280
GROW_EASING = "OutCubic"
CROSSFADE_MS = 110  # rect fades in as the chosen wedge fades out, over the start of the grow
FIELD_ARRIVE_MS = 90

WEDGE_BOX = 96  # square the rect grows out of, centered on the wedge's label
FIELD_WIDTH = 520
FIELD_HEIGHT = 56
FIELD_RADIUS = 8
FIELD_INSET_LEFT = 24
FIELD_INSET_RIGHT = 44  # the send hint sits in here
FIELD_FONT_SIZE = 12

FIELD_SURFACE = SURFACE_RAISED
FIELD_BORDER = BORDER_DIM
FIELD_BORDER_TYPING = BORDER_WARM  # one step warmer than idle
FIELD_BORDER_SENDING = ACCENT
FIELD_BORDER_REJECTED = "#8A5A5A"  # kept off the neutral ramp on purpose - the one functional error color, not decorative
FIELD_TEXT = BODY
FIELD_TEXT_SENDING = LABEL
FIELD_PLACEHOLDER = MUTED
FIELD_HINT_IDLE = HINT
FIELD_HINT_LIT = ACCENT

REJECT_MS = 90
REJECT_SHIFT = 4
REJECT_SHAKES = 2


# --- Claude chat card. claude-chat-flow.md's own palette and numbers - now
# also the app's palette everywhere else (see the shared primitives above),
# so the chat card no longer reads as a different surface from the ring. ---

CHAT_MONO_FAMILY = "Consolas"

CHAT_SURFACE = SURFACE  # card surface
CHAT_BORDER = BORDER_DIM  # card border, open
CHAT_BORDER_TAB = BORDER_STRONG  # card border, tabbed out at the edge
CHAT_COMPOSER_FIELD = SURFACE_RAISED
CHAT_ACCENT = ACCENT
CHAT_USER_BUBBLE = PALETTE["200"]  # the question's bubble - one step lighter than the card body
CHAT_BODY_TEXT = BODY
CHAT_LABEL_MONO = LABEL
CHAT_INERT_HINT = HINT

CHAT_BODY_SIZE = 12.5  # px, per claude-chat-flow.md's own px units
CHAT_HEADER_SIZE = 9.5  # px mono, 0.14em tracking (applied via QFont.setLetterSpacing, not CSS)
CHAT_HEADER_TRACKING_PERCENT = 114  # 1 + 0.14em, as QFont.PercentageSpacing wants it

CHAT_SIZE = 400
CHAT_MARGIN = 8 # from the work area's edges
CHAT_PADDING = SPACE_2  # 8px card-edge margin, shared by todo/notes/chat so they stay aligned

CHAT_FLIGHT_MS = 420
CHAT_FLIGHT_EASING = "OutCubic"  # deliberately no overshoot - next to a screen corner it reads as an error
CHAT_RADIUS_MS = 300  # the pill squares off before the flight ends, on the same curve
CHAT_RADIUS = 9
CHAT_DISMISS_MS = 140
CHAT_DISMISS_SLIDE = 24  # leaves toward the edge it rested against
CHAT_TYPING_PERIOD_MS = 900  # one full sweep of the pre-reply typing indicator's 3-dot pulse

CHAT_BUBBLE_RADIUS = (8, 8, 2, 8)  # top-left, top-right, bottom-right, bottom-left
CHAT_BUBBLE_PADDING_H = 9
CHAT_BUBBLE_PADDING_V = 7
CHAT_BUBBLE_MAX_WIDTH_FRACTION = 0.84
CHAT_BUBBLE_GAP_EXTRA = SPACE_3  # added on top of transcript_layout's own row spacing, only across a role change (user<->Bel), never between two turns from the same role
CHAT_REPLY_INSET = SPACE_2  # Bel's reply label stops this much short of contentWidth() - a deliberate visual margin instead of running flush with the composer's right edge
CHAT_PARAGRAPH_GAP = 6  # gap above a paragraph break *within* one Bel reply - deliberately smaller than the 8px turn-gap (transcript_layout's own spacing) so a break within a message never reads as bigger than the break between messages

CHAT_COMPOSER_HEIGHT = 2 * SPACE_4  # 32px, per claude-chat-flow.md's composer height


# --- Todo & note cards. Persistent, draggable squares toggled from the
# ring - same footprint, type, and neutral surface as the chat card (CHAT_*
# above) so all three read as one family; only their content differs. ---

CARD_BODY = PALETTE["000"]  # todo/chat card body - one step darker than the SURFACE header bar above it
CARD_DIVIDER = PALETTE["250"]  # notes' header/body seam (its body is lighter, not darker, than the header)
# and todo/chat's footer seam (their footer is the same CARD_BODY tone as the body, so only this line marks it)

TODO_DEFAULT_WIDTH = 340  # first-run width, per floating-card-redesign.md - still freely resizable after
NOTE_DEFAULT_WIDTH = 300

CARD_DRAG_THRESHOLD_PX = 4  # design.md's "press and move more than 4 px" - drag vs click/tick
CARD_AUTOSAVE_MS = 400  # idle debounce before writing position/content to disk

CARD_MIN_WIDTH = 200  # hard clamp, no max - resize-handle/spec.md
CARD_MIN_HEIGHT = 120  # hard clamp, no max

CARD_RESIZE_GRIP_HIT = 20  # bottom-right hit zone, square, px - bigger than the paint so it's easy to grab
CARD_RESIZE_GRIP_PAINT = 14  # painted glyph, square, px, inside the hit zone
CARD_RESIZE_GRIP_EDGE_OFFSET = 1  # hit zone sits this far inside the card's own corner (right/bottom)
CARD_RESIZE_GRIP_PAINT_OFFSET = 5  # painted glyph sits this far inside the card's own corner
CARD_RESIZE_GRIP_STROKE = 1.4  # logical px - never scaled by devicePixelRatio, see draggable.py
CARD_RESIZE_GRIP_REST = PALETTE["400"]  # ink at rest
CARD_RESIZE_GRIP_HOVER = LABEL  # ink on hover
CARD_RESIZE_GRIP_DRAG = BODY  # ink while dragging - instant, reverts on release
CARD_RESIZE_GRIP_HOVER_MS = 120
CARD_RESIZE_GRIP_HOVER_EASING = "OutCubic"
CARD_BORDER_DRAG = PALETTE["350"]  # card border while the grip is being dragged

CARD_SPAWN_OFFSET = 16  # cursor lands this far inside the card's corner when it opens
CARD_OPEN_MS = 160  # todo/note fade in over this long when picked from the ring

CARD_SHADOW_BLUR = 24
CARD_SHADOW_OFFSET_Y = 8
CARD_SHADOW_ALPHA = 115  # ~0.45, softened from design.md's result-card 0.55 to fit a modest CARD_SHADOW_MARGIN
RING_SHADOW_ALPHA = 60  # lower than CARD_SHADOW_ALPHA: a card's shadow only ever shows as a thin
# blurred fringe outside its own opaque body, but the ring paints its shadow as a visible band
# across the donut itself (gaps between wedges, the dead-zone hole), so the same alpha would read
# far heavier than the cards' - toned down here to land at the same subtle-but-visible depth.
CARD_SHADOW_MARGIN = 28  # extra room a top-level card window needs on every side so its own
# QGraphicsDropShadowEffect isn't clipped at the window's edge - unlike a shadow on a child
# widget (promptBar.py's, which bleeds into its parent overlay), a top-level window's effect
# can only paint within that window's own pixels.

CARD_EDGE_MARGIN = CHAT_MARGIN - CARD_SHADOW_MARGIN  # screenBounds clamp margin for todo/notes/
# settings windows: their window rect is padded by CARD_SHADOW_MARGIN beyond the visible card
# face, so clamping the window itself to CHAT_MARGIN would leave the *visible* face CHAT_MARGIN
# + CARD_SHADOW_MARGIN from the screen edge - correcting by CARD_SHADOW_MARGIN here keeps the
# visible corner at CHAT_MARGIN, same as the chat card's own dock position.

TODO_ROW_HEIGHT = 36
TODO_CHECKBOX = 17
TODO_CHECKBOX_RADIUS = 4
TODO_REMOVE_DELAY_MS = 1000  # a ticked row vanishes this long after being checked, unless unticked first
TODO_ITEM_FADE_MS = 180  # a ticked row fades out over this long before it's actually removed


# --- Settings card. A short, fixed list of the ring's non-pinned wedges -
# label, assigned action, reorder - same CHAT_* surface/shadow as
# todo/note/chat so it reads as one family. No resize grip: the row count
# never grows past wedgeConfig.DEFAULT_OTHER_WEDGES's length. ---

SETTINGS_WIDTH = CHAT_SIZE
SETTINGS_HEADER_HEIGHT = 24
SETTINGS_ROW_HEIGHT = 32
SETTINGS_ROW_GAP = 8
SETTINGS_ARROW_SIZE = 22
SETTINGS_ROWS = 3  # todo, note, claude - wedgeConfig.DEFAULT_OTHER_WEDGES's length
SETTINGS_CONTEXT_FIELD_WIDTH = 48
SETTINGS_HEIGHT = (
    SETTINGS_HEADER_HEIGHT
    + 10
    + SETTINGS_ROWS * SETTINGS_ROW_HEIGHT
    + (SETTINGS_ROWS - 1) * SETTINGS_ROW_GAP
    + SETTINGS_ROW_GAP + SETTINGS_ROW_HEIGHT  # the Claude context-limit field below the rows
    + 2 * CHAT_PADDING
)


# --- Edge dock. The chat card's right-edge proximity behaviour: OPEN, or
# HIDDEN (reached only by an explicit minimize, never automatically); a TAB
# peeks back out on approach while HIDDEN. Kept separate from CHAT_* above
# since these drive claudeEdgeDockState.py's pure state machine, not the
# card's own paint. ---

DOCK_COMPACT_SIZE = 64  # HIDDEN/TAB's puck footprint
DOCK_TAB_VISIBLE_PX = 26  # how much of the puck still shows in TAB
DOCK_TAB_ROTATION_DEG = -9.0  # float: must match self.tilt's type or QVariantAnimation won't interpolate
DOCK_TAB_SLIDE_MS = 300
DOCK_TAB_ROTATE_MS = 260

DOCK_OPEN_MS = 300  # animating to OPEN, from HIDDEN or TAB
DOCK_HIDE_MS = 300  # OPEN -> HIDDEN, sliding fully past the edge

CHAT_DOCK_SNAP_MS = 220  # drag-and-snap's release -> corner tween - quicker and bouncier than DOCK_OPEN_MS's
# HIDDEN/TAB -> OPEN tween, since this is a deliberate "magnetic" gesture, not a flight landing next to a
# corner (CHAT_FLIGHT_EASING's own "no overshoot" reasoning doesn't apply here).
CHAT_DOCK_SNAP_EASING = "OutBack"
CHAT_DOCK_SNAP_OVERSHOOT = 1.2

DOCK_ARM_PX = 180  # cursor closer than this to the right edge arms the tab
DOCK_DISARM_PX = 260  # and must retreat past this to disarm - the hysteresis gap

DOCK_TRIGGER_WIDTH = 180  # EdgeTrigger's width along the right edge


# --- Resolution scaling. Every constant above was tuned by eye at
# REFERENCE_WIDTH x REFERENCE_HEIGHT; apply_scale() multiplies the ones that
# are raw pixel lengths so the UI stays proportional on other screens. Colors,
# alphas, ms durations, dimensionless ratios, easing names, counts, and
# degree angles are left untouched - they don't scale with resolution.
# Not applied at import time (every test imports this module directly and
# asserts exact pixel values against these reference numbers) - only
# main.py calls this, once, after QApplication exists. ---

REFERENCE_WIDTH = 2560
REFERENCE_HEIGHT = 1440

_SCALE_INT_NAMES = [
    "SPACE_1", "SPACE_2", "SPACE_3", "SPACE_4",
    "RING_RADIUS", "GLOW_WIDTH", "WEDGE_BOX",
    "FIELD_WIDTH", "FIELD_HEIGHT", "FIELD_RADIUS", "FIELD_INSET_LEFT", "FIELD_INSET_RIGHT",
    "FIELD_FONT_SIZE", "FONT_SIZE",
    "REJECT_SHIFT",
    "CHAT_SIZE", "CHAT_MARGIN", "CHAT_PADDING", "CHAT_RADIUS",
    "CHAT_DISMISS_SLIDE", "CHAT_BUBBLE_PADDING_H", "CHAT_BUBBLE_PADDING_V",
    "CHAT_BUBBLE_GAP_EXTRA", "CHAT_REPLY_INSET", "CHAT_PARAGRAPH_GAP",
    "CHAT_COMPOSER_HEIGHT",
    "TODO_DEFAULT_WIDTH", "NOTE_DEFAULT_WIDTH",
    "CARD_DRAG_THRESHOLD_PX", "CARD_MIN_WIDTH", "CARD_MIN_HEIGHT",
    "CARD_RESIZE_GRIP_HIT", "CARD_RESIZE_GRIP_PAINT",
    "CARD_RESIZE_GRIP_EDGE_OFFSET", "CARD_RESIZE_GRIP_PAINT_OFFSET",
    "CARD_SPAWN_OFFSET", "CARD_SHADOW_BLUR", "CARD_SHADOW_OFFSET_Y",
    "CARD_SHADOW_MARGIN", "CARD_EDGE_MARGIN",
    "TODO_ROW_HEIGHT", "TODO_CHECKBOX", "TODO_CHECKBOX_RADIUS",
    "SETTINGS_WIDTH", "SETTINGS_HEADER_HEIGHT", "SETTINGS_ROW_HEIGHT",
    "SETTINGS_ROW_GAP", "SETTINGS_ARROW_SIZE", "SETTINGS_CONTEXT_FIELD_WIDTH",
    "SETTINGS_HEIGHT",
    "DOCK_COMPACT_SIZE", "DOCK_TAB_VISIBLE_PX", "DOCK_ARM_PX", "DOCK_DISARM_PX",
    "DOCK_TRIGGER_WIDTH",
]

# Already floats in their reference form - scaled but kept as floats, not
# rounded to int.
_SCALE_FLOAT_NAMES = ["CHAT_BODY_SIZE", "CHAT_HEADER_SIZE", "CARD_RESIZE_GRIP_STROKE"]

# Tuples of pixel lengths - each element scaled and rounded individually.
_SCALE_INT_TUPLE_NAMES = ["CHAT_BUBBLE_RADIUS"]


def apply_scale(factor):
    g = globals()
    for name in _SCALE_INT_NAMES:
        g[name] = round(g[name] * factor)
    for name in _SCALE_FLOAT_NAMES:
        g[name] = g[name] * factor
    for name in _SCALE_INT_TUPLE_NAMES:
        g[name] = tuple(round(v * factor) for v in g[name])


def prompt_field_stylesheet(text_color):
    return (
        "background: transparent;"
        "border: none;"
        f"color: {text_color};"
        f"font-family: {FONT_FAMILY};"
        f"font-size: {FIELD_FONT_SIZE}pt;"
        f"selection-background-color: {ACCENT};"
        f"selection-color: {LABEL_HOVER};"
    )


def card_border_color(dragging):
    """The resizable cards' (note/todo) frame border - shifts while the
    resize grip is being dragged, per resize-handle/spec.md."""
    return CARD_BORDER_DRAG if dragging else CHAT_BORDER


def chat_close_stylesheet():
    return (
        f"QPushButton {{ color: {CHAT_LABEL_MONO}; background: transparent; border: none; }}"
        f"QPushButton:hover {{ color: {CHAT_BODY_TEXT}; }}"
    )


def chat_scrollbar_stylesheet():
    return (
        "QScrollArea { background: transparent; border: none; }"
        "QScrollArea > QWidget > QWidget { background: transparent; }"
        "QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }"
        f"QScrollBar::handle:vertical {{ background: {CHAT_BORDER}; border-radius: 3px; min-height: 24px; }}"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }"
    )


def chat_turn_stylesheet():
    # Full CHAT_BODY_TEXT brightness rather than a dimmer secondary tone -
    # Bel's reply is the thing being read here, so it shouldn't be styled
    # as lower-priority than the user's own bubble text.
    return f"color: {CHAT_BODY_TEXT}; font-family: {FONT_FAMILY}; font-size: {CHAT_BODY_SIZE}px; background: transparent;"


def chat_bubble_stylesheet():
    tl, tr, br, bl = CHAT_BUBBLE_RADIUS
    return (
        f"background: {CHAT_USER_BUBBLE}; color: {CHAT_BODY_TEXT};"
        f"font-family: {FONT_FAMILY}; font-size: {CHAT_BODY_SIZE}px;"
        f"padding: {CHAT_BUBBLE_PADDING_V}px {CHAT_BUBBLE_PADDING_H}px;"
        f"border-top-left-radius: {tl}px; border-top-right-radius: {tr}px;"
        f"border-bottom-right-radius: {br}px; border-bottom-left-radius: {bl}px;"
    )


def plain_field_stylesheet():
    """A flat field with no box of its own: notes' body, and todo/chat's
    footer row, since in both cases the card itself paints the background
    and any border/seam around it (see FloatingCard subclasses' paintEvent /
    ChatCard.paintFrame)."""
    return (
        "background: transparent; border: none;"
        f"color: {CHAT_BODY_TEXT}; font-family: {FONT_FAMILY}; font-size: {CHAT_BODY_SIZE}px;"
    )


def settings_field_stylesheet():
    return (
        f"background: {CHAT_COMPOSER_FIELD}; color: {CHAT_BODY_TEXT};"
        f"font-family: {FONT_FAMILY}; font-size: {CHAT_BODY_SIZE}px;"
        f"border: 1px solid {CHAT_INERT_HINT}; border-radius: 6px;"
        "padding: 0 8px;"
    )


def settings_combo_stylesheet():
    return (
        f"QComboBox {{ background: {CHAT_COMPOSER_FIELD}; color: {CHAT_BODY_TEXT};"
        f"font-family: {FONT_FAMILY}; font-size: {CHAT_BODY_SIZE}px;"
        f"border: 1px solid {CHAT_INERT_HINT}; border-radius: 6px; padding: 0 8px; }}"
        f"QComboBox QAbstractItemView {{ background: {CHAT_SURFACE}; color: {CHAT_BODY_TEXT};"
        f"selection-background-color: {CHAT_USER_BUBBLE}; border: 1px solid {CHAT_BORDER}; }}"
    )


def settings_arrow_stylesheet():
    return (
        f"QPushButton {{ color: {CHAT_LABEL_MONO}; background: transparent; border: none; }}"
        f"QPushButton:hover {{ color: {CHAT_BODY_TEXT}; }}"
        f"QPushButton:disabled {{ color: {CHAT_INERT_HINT}; }}"
    )


def overlay_stylesheet():
    return (
        f"background-color: {BACKGROUND};"
        f"color: {TEXT};"
        f"font-family: {FONT_FAMILY};"
        f"font-size: {FONT_SIZE}pt;"
        f"border: 1px solid {BORDER};"
        "border-radius: 8px;"
    )
