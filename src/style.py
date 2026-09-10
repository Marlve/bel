# Centralized colors and fonts for every overlay. Change a value here, not per-window.

BACKGROUND = "#1e1e2edd"
TEXT = "#f5f5f5"
ACCENT = "#89b4fa"
BORDER = "#313244"

FONT_FAMILY = "Segoe UI"
FONT_SIZE = 11

PIE_RADIUS = 140
PIE_DEADZONE = 80


def overlay_stylesheet():
    return (
        f"background-color: {BACKGROUND};"
        f"color: {TEXT};"
        f"font-family: {FONT_FAMILY};"
        f"font-size: {FONT_SIZE}pt;"
        f"border: 1px solid {BORDER};"
        "border-radius: 8px;"
    )
