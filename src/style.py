# Centralized colors, sizes and motion for every overlay. Change a value here, not per-window.

# --- Shared neutral palette. One grayscale system - ring, prompt bar, and
# chat card all read from these same primitives, the way claude-chat-flow.md
# specified for the chat card alone. No hue anywhere; "accent" is near-white,
# not a color. ---

SURFACE = "#17181A"  # darkest surface: wedge idle fill, chat card body
SURFACE_RAISED = "#1B1C1F"  # one step up: prompt field, composer
SURFACE_BUBBLE = "#24252A"  # user bubble, pressed wedge fill
BORDER_DIM = "#2D2E31"  # resting border, one step lighter than its surface
BORDER_WARM = "#3E3F44"  # border once there's content/typing
BORDER_STRONG = "#4C4D52"  # strongest border (tabbed-out dock state)
HINT = "#3C3D41"  # inert icons/hints
MUTED = "#6B6C70"  # placeholder text, dimmed secondary text
LABEL = "#86878B"  # mono labels, muted body text
BODY_DIM = "#C8C9CD"  # secondary/idle text
BODY = "#E8E8EA"  # primary text
INK = "#0B0C10"  # near-black, for text on top of the accent
ACCENT_NEUTRAL = "#D8D9DC"  # the one accent - near-white, not a hue

BACKGROUND = SURFACE + "dd"
TEXT = BODY
ACCENT = ACCENT_NEUTRAL
BORDER = BORDER_DIM

FONT_FAMILY = "Segoe UI"
FONT_SIZE = 11


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
CHAT_COMPOSER_BORDER_WARM = BORDER_WARM  # on content
CHAT_ACCENT = ACCENT
CHAT_USER_BUBBLE = SURFACE_BUBBLE
CHAT_BODY_TEXT = BODY
CHAT_TURN_TEXT = BODY_DIM  # claude's own turns - plain text, no bubble
CHAT_LABEL_MONO = LABEL
CHAT_INERT_HINT = HINT

CHAT_BODY_SIZE = 12.5  # px, per claude-chat-flow.md's own px units
CHAT_HEADER_SIZE = 9.5  # px mono, 0.14em tracking (applied via QFont.setLetterSpacing, not CSS)
CHAT_HEADER_TRACKING_PERCENT = 114  # 1 + 0.14em, as QFont.PercentageSpacing wants it

CHAT_SIZE = 340
CHAT_MARGIN = 24  # from the work area's edges
CHAT_PADDING = 14

CHAT_FLIGHT_MS = 420
CHAT_FLIGHT_EASING = "OutCubic"  # deliberately no overshoot - next to a screen corner it reads as an error
CHAT_RADIUS_MS = 300  # the pill squares off before the flight ends, on the same curve
CHAT_RADIUS = 10
CHAT_DISMISS_MS = 140
CHAT_DISMISS_SLIDE = 24  # leaves toward the edge it rested against

CHAT_BUBBLE_RADIUS = (9, 9, 3, 9)  # top-left, top-right, bottom-right, bottom-left
CHAT_BUBBLE_PADDING_H = 9
CHAT_BUBBLE_PADDING_V = 7
CHAT_BUBBLE_MAX_WIDTH_FRACTION = 0.84

CHAT_COMPOSER_HEIGHT = 32
CHAT_COMPOSER_PADDING = 11


# --- Todo & note cards. Persistent, draggable squares toggled from the
# ring - same footprint, type, and neutral surface as the chat card (CHAT_*
# above) so all three read as one family; only their content differs. ---

CARD_DRAG_THRESHOLD_PX = 4  # design.md's "press and move more than 4 px" - drag vs click/tick
CARD_AUTOSAVE_MS = 400  # idle debounce before writing position/content to disk

CARD_MIN_SIZE = 220  # never smaller than this in either dimension
CARD_RESIZE_GRIP = 16  # bottom-right corner handle, square, px
CARD_SPAWN_OFFSET = 16  # cursor lands this far inside the card's corner when it opens
CARD_OPEN_MS = 160  # todo/note fade in over this long when picked from the ring

CARD_SHADOW_BLUR = 24
CARD_SHADOW_OFFSET_Y = 8
CARD_SHADOW_ALPHA = 115  # ~0.45, softened from design.md's result-card 0.55 to fit a modest CARD_SHADOW_MARGIN
CARD_SHADOW_MARGIN = 28  # extra room a top-level card window needs on every side so its own
# QGraphicsDropShadowEffect isn't clipped at the window's edge - unlike a shadow on a child
# widget (promptBar.py's, which bleeds into its parent overlay), a top-level window's effect
# can only paint within that window's own pixels.

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


# --- Edge dock. The chat card's right-edge proximity behaviour: OPEN, folds
# to a COMPACT puck, then slides fully HIDDEN; a TAB peeks back out on
# approach. Kept separate from CHAT_* above since these drive claudeEdgeDock.py's
# pure state machine, not the card's own paint. ---

DOCK_COMPACT_SIZE = 64
DOCK_TAB_VISIBLE_PX = 26  # how much of the puck still shows in TAB
DOCK_TAB_ROTATION_DEG = -9.0  # float: must match self.tilt's type or QVariantAnimation won't interpolate
DOCK_TAB_SLIDE_MS = 300
DOCK_TAB_ROTATE_MS = 260

DOCK_COMPACT_MS = 300  # OPEN -> COMPACT, folding in place
DOCK_COMPACT_TO_HIDE_DELAY_MS = 220  # pause between folding and sliding off
DOCK_HIDE_MS = 300  # COMPACT -> HIDDEN, sliding fully past the edge

DOCK_ARM_PX = 180  # cursor closer than this to the right edge arms the tab
DOCK_DISARM_PX = 260  # and must retreat past this to disarm - the hysteresis gap

DOCK_IDLE_MS = 6_000  # before the compact step, with nothing else going on
DOCK_LEAVE_MS = 2_500  # after the cursor leaves an open card

DOCK_TRIGGER_WIDTH = 180  # EdgeTrigger's width along the right edge


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
    return f"color: {CHAT_TURN_TEXT}; font-family: {FONT_FAMILY}; font-size: {CHAT_BODY_SIZE}px; background: transparent;"


def chat_bubble_stylesheet():
    tl, tr, br, bl = CHAT_BUBBLE_RADIUS
    return (
        f"background: {CHAT_USER_BUBBLE}; color: {CHAT_BODY_TEXT};"
        f"font-family: {FONT_FAMILY}; font-size: {CHAT_BODY_SIZE}px;"
        f"padding: {CHAT_BUBBLE_PADDING_V}px {CHAT_BUBBLE_PADDING_H}px;"
        f"border-top-left-radius: {tl}px; border-top-right-radius: {tr}px;"
        f"border-bottom-right-radius: {br}px; border-bottom-left-radius: {bl}px;"
    )


def note_body_stylesheet():
    return (
        "background: transparent; border: none;"
        f"color: {CHAT_BODY_TEXT}; font-family: {FONT_FAMILY}; font-size: {CHAT_BODY_SIZE}px;"
    )


def chat_composer_stylesheet(warm):
    border = CHAT_COMPOSER_BORDER_WARM if warm else CHAT_INERT_HINT
    return (
        f"background: {CHAT_COMPOSER_FIELD}; color: {CHAT_BODY_TEXT};"
        f"font-family: {FONT_FAMILY}; font-size: {CHAT_BODY_SIZE}px;"
        f"border: 1px solid {border}; border-radius: {CHAT_COMPOSER_HEIGHT // 2}px;"
        f"padding: 0 {CHAT_COMPOSER_PADDING}px;"
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
