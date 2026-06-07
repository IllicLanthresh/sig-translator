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
    QWidget {{
        background: {BG};
        color: {TEXT};
        font-family: "Bahnschrift", "Segoe UI", sans-serif;
        font-size: 14px;
    }}
    QFrame#Card, QWidget#Card {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 12px;
    }}
    QLabel#H1 {{ font-size: 20px; font-weight: 700; }}
    QLabel#H2 {{ font-size: 15px; font-weight: 700; }}
    QLabel#Muted {{ color: {MUTED}; }}

    /* Sidebar nav */
    QListWidget#Nav {{
        background: {PANEL};
        border: none;
        border-right: 1px solid {BORDER};
        outline: 0;
        padding: 10px 8px;
    }}
    QListWidget#Nav::item {{
        padding: 10px 14px;
        border-radius: 10px;
        margin: 2px 4px;
        color: {MUTED};
    }}
    QListWidget#Nav::item:selected {{
        background: {PANEL_2};
        color: {accent};
        font-weight: 700;
    }}
    QListWidget#Nav::item:hover {{ background: {PANEL_2}; }}

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
