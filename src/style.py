# Centralized colors, sizes and motion for every overlay. Change a value here, not per-window.

BACKGROUND = "#1e1e2edd"
TEXT = "#f5f5f5"
ACCENT = "#89b4fa"
BORDER = "#313244"

FONT_FAMILY = "Segoe UI"
FONT_SIZE = 11


# --- Pie menu ring. Sizes are ratios of RING_RADIUS so the ring scales as one. ---

RING_RADIUS = 168
RING_INNER = 0.35  # donut hole; the cursor inside it selects nothing
RING_HIT_OUTER = 1.3  # cursor past this selects nothing - a bit of slack past the ring's ink, not much
RING_LABEL = 0.68  # label centroid distance from the center

WEDGE_IDLE = "#171B24"
WEDGE_BORDER = "#242C3A"
WEDGE_HOVER = "#8AB4FF"
WEDGE_PRESSED = "#6E97E3"
LABEL_IDLE = "#B4BDD0"
LABEL_HOVER = "#0B0C10"
SCRIM = "#000000"
SCRIM_ALPHA = 0.55
GLOW = "#8AB4FF"
GLOW_ALPHA = 0.22
GLOW_WIDTH = 18

# Open: ring pops out of the cursor, wedges arriving one after another.
OPEN_MS = 430
OPEN_SCALE_FROM = 0.30
OPEN_EASING = "OutBack"
OPEN_OVERSHOOT = 1.56
OPEN_FADE_MS = 170  # opacity lands well before the scale does, so it reads as arriving
OPEN_FADE_EASING = "OutCubic"
OPEN_STAGGER_MS = 26
SCRIM_MS = 220

# Hover: only the hovered wedge moves - it slides outward and grows a little.
HOVER_IN_MS = 140
HOVER_IN_EASING = "OutBack"
HOVER_IN_OVERSHOOT = 1.15
HOVER_OUT_MS = 110
HOVER_OUT_EASING = "OutCubic"
HOVER_PUSH = 0.07
HOVER_GROW = 1.035
LABEL_HOVER_SCALE = 1.08

# Select: the others drop away fast, the chosen wedge pushes out and holds alone before closing.
SELECT_OTHERS_MS = 120
SELECT_OTHERS_SCALE = 0.88
SELECT_OTHERS_ALPHA = 0.12
SELECT_HOLD_MS = 150
SELECT_PUSH = 0.15
SELECT_SCALE = 1.06
SELECT_EASING = "OutCubic"

# Close: whole ring shrinks back and fades, no bounce.
CLOSE_MS = 150
CLOSE_SCALE_TO = 0.30
CLOSE_EASING = "InQuad"


# --- Prompt bar. A wedge that needs typed input hands off to a text field
# instead of firing straight away, so the ring gets its own shorter exit and
# one rounded rect grows out of the wedge into the field. ---

RING_EXIT_MS = 130
RING_EXIT_HOLD_MS = 60  # chosen wedge holds its hover pose this long first, so the click registers
RING_EXIT_SCALE = 0.30
RING_EXIT_EASING = "InQuad"
GROW_MS = 280
GROW_EASING = "OutCubic"
CROSSFADE_MS = 110  # rect fades in as the chosen wedge fades out, over the start of the grow
FIELD_ARRIVE_MS = 90

WEDGE_BOX = 96  # square the rect grows out of, centered on the wedge's label
FIELD_WIDTH = 520
FIELD_HEIGHT = 56
FIELD_INSET_LEFT = 58  # the mark sits in here
FIELD_INSET_RIGHT = 44  # so does the send hint
FIELD_MARK = 24
FIELD_MARK_INSET = 26  # from the field's left cap
FIELD_FONT_SIZE = 12

FIELD_SURFACE = "#141924"
FIELD_BORDER = "#2A3243"
FIELD_BORDER_TYPING = "#37415A"  # one step warmer than idle
FIELD_BORDER_SENDING = ACCENT
FIELD_BORDER_REJECTED = "#8A5A5A"
FIELD_TEXT = "#E6EAF2"
FIELD_TEXT_SENDING = "#8B93A5"
FIELD_PLACEHOLDER = "#6B7488"
FIELD_HINT_IDLE = "#454E63"
FIELD_HINT_LIT = ACCENT

REJECT_MS = 90
REJECT_SHIFT = 4
REJECT_SHAKES = 2


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


def overlay_stylesheet():
    return (
        f"background-color: {BACKGROUND};"
        f"color: {TEXT};"
        f"font-family: {FONT_FAMILY};"
        f"font-size: {FONT_SIZE}pt;"
        f"border: 1px solid {BORDER};"
        "border-radius: 8px;"
    )
