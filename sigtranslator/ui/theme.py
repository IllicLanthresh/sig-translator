"""Dark sci-fi QSS theme for the Qt app. Accent is injected at runtime."""

from __future__ import annotations

# Base palette
BG = "#0e1116"        # window background
PANEL = "#161b22"     # cards / panels
PANEL_2 = "#1c232c"   # raised / hover
BORDER = "#2a323c"
TEXT = "#e6edf3"
MUTED = "#9aa4b0"


def qss(accent: str = "#7fdfff") -> str:
    return f"""
    QMainWindow, QWidget#Page {{ background: {BG}; }}
    QWidget {{
        color: {TEXT};
        font-family: "Bahnschrift", "Segoe UI", sans-serif;
        font-size: 14px;
    }}
    QLabel, QCheckBox {{ background: transparent; }}
    QFrame#Card, QWidget#Card {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 12px;
    }}
    QLabel#H1 {{ font-size: 20px; font-weight: 700; }}
    QLabel#H2 {{ font-size: 15px; font-weight: 700; }}
    QLabel#Muted {{ color: {MUTED}; }}

    /* Header bar */
    QWidget#Header {{
        background: {PANEL};
        border-bottom: 1px solid {BORDER};
    }}
    QPushButton#Ghost {{
        background: transparent;
        border: none;
        color: {MUTED};
        font-size: 17px;
        padding: 4px 10px;
    }}
    QPushButton#Ghost:hover {{ color: {accent}; }}

    /* Segmented two-side toggles (e.g. GUI only | GUI + in-game) */
    QPushButton#SegLeft, QPushButton#SegRight {{
        background: {PANEL_2};
        border: 1px solid {BORDER};
        color: {MUTED};
        padding: 4px 10px;
        font-size: 12px;
    }}
    QPushButton#SegLeft {{
        border-top-left-radius: 8px; border-bottom-left-radius: 8px;
        border-top-right-radius: 0; border-bottom-right-radius: 0;
    }}
    QPushButton#SegRight {{
        border-top-right-radius: 8px; border-bottom-right-radius: 8px;
        border-top-left-radius: 0; border-bottom-left-radius: 0;
        border-left: none;
    }}
    QPushButton#SegLeft:hover, QPushButton#SegRight:hover {{ border-color: {accent}; }}
    QPushButton#SegLeft:checked, QPushButton#SegRight:checked {{
        background: {accent};
        color: #06121a;
        font-weight: 700;
    }}

    /* Scanner switches: dim when off, accent when scanning */
    QPushButton#Scanner {{
        background: {PANEL_2};
        border: 1px solid {BORDER};
        color: {MUTED};
        font-weight: 700;
    }}
    QPushButton#Scanner:hover {{ border-color: {accent}; }}
    QPushButton#Scanner:checked {{
        background: {accent};
        color: #06121a;
        border: none;
    }}

    /* Buttons */
    QPushButton {{
        background: {PANEL_2};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 8px 14px;
        color: {TEXT};
    }}
    QPushButton:hover {{ border-color: {accent}; }}
    QPushButton#Primary {{
        background: {accent};
        color: #06121a;
        border: none;
        font-weight: 700;
    }}
    QPushButton#Primary:hover {{ background: {accent}; }}

    QComboBox {{
        background: {PANEL_2};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 6px 10px;
    }}
    QComboBox:hover {{ border-color: {accent}; }}
    QComboBox QAbstractItemView {{
        background: {PANEL_2};
        border: 1px solid {BORDER};
        selection-background-color: {accent};
        selection-color: #06121a;
    }}
    QCheckBox {{ spacing: 8px; }}
    """
