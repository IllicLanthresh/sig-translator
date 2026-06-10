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

    /* Live-mirror stages (dark canvas behind the overlay mirrors) */
    QFrame#Stage {{
        background: #0a0d12;
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}
    QPushButton#Pill {{
        background: transparent;
        border: 1px solid {BORDER};
        border-radius: 13px;
        padding: 4px 14px;
        color: {MUTED};
        font-size: 12px;
        font-weight: 700;
    }}
    QPushButton#Pill:hover {{ border-color: {accent}; }}
    QPushButton#Pill:checked {{ color: {accent}; border-color: {accent}; }}

    /* Rail footer chips + turret rows */
    QPushButton#Chip {{
        background: {PANEL_2};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 4px 10px;
        color: {MUTED};
        font-size: 12px;
    }}
    QPushButton#Chip:hover {{ border-color: {accent}; }}
    QPushButton#TurretRow {{
        background: transparent;
        border: none;
        text-align: left;
        padding: 4px 6px;
        border-radius: 6px;
    }}
    QPushButton#TurretRow:hover {{ background: {PANEL_2}; }}

    /* Drawer submenus */
    QFrame#Drawer {{
        background: {PANEL};
        border-left: 1px solid {BORDER};
    }}
    QWidget#Scrim {{ background: rgba(0, 0, 0, 140); }}

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
