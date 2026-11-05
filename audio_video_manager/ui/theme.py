"""Design system AVM-08E — Brume pastel (direction A validée)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from audio_video_manager.ui.fonts import display_font_family, load_embedded_fonts, ui_font_family

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

# Palette officielle + surfaces laiteuses (prototype a-brume-pastel)
TOKEN = {
    "bg": "#17191F",  # anthracite : contraste / sous-couche si image absente
    "bg_mist": "#F0EBE3",
    "surface": "rgba(255, 252, 248, 0.72)",
    "surface_solid": "#FFFCF8",
    "elev": "rgba(255, 250, 245, 0.88)",
    "elev_solid": "#FFFAF5",
    "nav": "rgba(255, 250, 245, 0.55)",
    "ink": "#2A2E3A",
    "ink_title": "#17191F",
    "muted": "#5C6478",
    "accent": "#F1B65C",
    "accent_hover": "#E0A44A",
    "accent_soft": "rgba(241, 182, 92, 0.28)",
    "accent_chip": "rgba(88, 185, 170, 0.22)",
    "nav_active_ink": "#6B4A12",
    "iris": "#7D8FE8",
    "rose": "#D782A6",
    "jade": "#58B9AA",
    "border": "rgba(45, 52, 70, 0.12)",
    "border_strong": "rgba(45, 52, 70, 0.20)",
    "warn_bg": "rgba(241, 182, 92, 0.22)",
    "warn_ink": "#6B4A12",
    "err_bg": "rgba(215, 130, 166, 0.20)",
    "err_ink": "#8A3A5C",
    "ok": "#1F6B60",
    "ok_ink": "#1F6B60",
    "danger": "#D782A6",
    "primary_ink": "#17191F",
    "radius": "28px",
    "radius_sm": "16px",
    "font": '"Outfit", "Segoe UI", "Segoe UI Variable", sans-serif',
    "font_display": '"Fraunces", "Segoe UI Semibold", Georgia, serif',
}


def _build_app_style() -> str:
    ui = ui_font_family()
    display = display_font_family()
    t = dict(TOKEN)
    t["font"] = f'"{ui}", "Segoe UI", sans-serif'
    t["font_display"] = f'"{display}", Georgia, serif'
    return f"""
* {{
  font-family: {t["font"]};
}}

QMainWindow {{
  background: {t["bg_mist"]};
  color: {t["ink"]};
  font-size: 13px;
}}

QWidget#centralRoot {{
  background: transparent;
  color: {t["ink"]};
}}

QWidget#sideRail {{
  background: {t["nav"]};
  border: 1px solid {t["border"]};
  border-radius: {t["radius"]};
}}

QLabel#brandMark {{
  font-family: {t["font_display"]};
  font-size: 18px;
  font-weight: 600;
  color: {t["ink_title"]};
  letter-spacing: -0.3px;
}}
QLabel#brandAccent {{
  font-family: {t["font_display"]};
  font-size: 18px;
  font-weight: 600;
  color: {t["accent"]};
  letter-spacing: -0.3px;
}}
QLabel#sideBrandSub {{
  color: {t["muted"]};
  font-size: 11px;
}}

QLabel#pageTitle, QLabel#wizardTitle, QLabel#heroTitle {{
  font-family: {t["font_display"]};
  font-size: 26px;
  font-weight: 600;
  color: {t["ink_title"]};
  letter-spacing: -0.4px;
  padding: 2px 0 6px 0;
}}
QLabel#heroSub {{
  font-size: 14px;
  color: {t["muted"]};
}}

QPushButton#sideNavBtn {{
  background: transparent;
  border: none;
  color: {t["muted"]};
  font-weight: 600;
  font-size: 13px;
  text-align: left;
  padding: 12px 14px;
  min-height: 40px;
  border-radius: 14px;
}}
QPushButton#sideNavBtn:hover {{
  color: {t["ink"]};
  background: rgba(125, 143, 232, 0.14);
}}
QPushButton#sideNavBtn[active="true"] {{
  background: {t["accent_soft"]};
  color: {t["nav_active_ink"]};
}}
QPushButton#sideNavBtn:focus {{
  border: 2px solid {t["iris"]};
  outline: none;
}}
QPushButton#sideNavBtn:disabled {{
  color: #9AA3B5;
}}

QListWidget#navList, QTabBar#navTabs {{
  max-height: 0;
  max-width: 0;
  border: none;
  background: transparent;
}}

QFrame#card, QFrame[card="true"] {{
  background: {t["surface"]};
  border: 1px solid {t["border"]};
  border-radius: 24px;
}}

QWidget#contentStage {{
  background: {t["surface"]};
  border: 1px solid {t["border"]};
  border-radius: {t["radius"]};
}}

QLabel#cardTitle {{
  font-family: {t["font_display"]};
  font-size: 16px;
  font-weight: 600;
  color: {t["ink_title"]};
}}
QLabel#chip, QLabel[chip="ok"] {{
  background: rgba(255, 252, 248, 0.92);
  color: {t["ok"]};
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
}}
QLabel#chipWarn, QLabel[chip="warn"] {{
  background: {t["warn_bg"]};
  color: {t["warn_ink"]};
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
}}
QLabel#chipErr, QLabel[chip="err"] {{
  background: {t["err_bg"]};
  color: {t["err_ink"]};
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
}}

QPushButton {{
  min-height: 32px;
  padding: 8px 16px;
  border-radius: {t["radius_sm"]};
  border: 1px solid {t["border"]};
  background: {t["elev"]};
  color: {t["ink"]};
}}
QPushButton:hover {{ background: rgba(255, 255, 255, 0.85); }}
QPushButton:focus {{
  border: 2px solid {t["iris"]};
  outline: none;
}}
QPushButton:disabled {{
  color: #9AA3B5;
  background: rgba(255, 250, 245, 0.45);
  border-color: {t["border"]};
}}

QPushButton[primary="true"], QPushButton#primary {{
  background: {t["accent"]};
  color: {t["primary_ink"]};
  border: none;
  border-radius: {t["radius_sm"]};
  padding: 10px 18px;
  min-height: 36px;
  font-weight: 700;
}}
QPushButton[primary="true"]:hover, QPushButton#primary:hover {{
  background: {t["accent_hover"]};
}}
QPushButton[primary="true"]:focus, QPushButton#primary:focus {{
  border: 2px solid {t["iris"]};
}}
QPushButton[primary="true"]:disabled, QPushButton#primary:disabled {{
  background: #D5CBB8;
  color: #7A7468;
}}

QPushButton[ghost="true"], QPushButton#ghost {{
  background: rgba(255, 255, 255, 0.35);
  border: 1px solid {t["border"]};
  border-radius: 999px;
  padding: 9px 16px;
  min-height: 36px;
  color: {t["muted"]};
}}
QPushButton[ghost="true"]:hover, QPushButton#ghost:hover {{
  background: rgba(125, 143, 232, 0.14);
  color: {t["ink"]};
}}

QPushButton[step="true"] {{
  border: none;
  background: {t["elev"]};
  color: {t["muted"]};
  padding: 8px 14px;
  min-height: 30px;
  border-radius: 14px;
  font-size: 12px;
  text-align: left;
}}
QPushButton[step="true"][done="true"] {{
  background: rgba(125, 143, 232, 0.18);
  color: #3A4A8B;
  font-weight: 600;
}}
QPushButton[step="true"][active="true"] {{
  background: {t["accent_soft"]};
  color: {t["nav_active_ink"]};
  font-weight: 700;
}}
QPushButton[step="true"]:focus {{
  border: 2px solid {t["iris"]};
}}

QLabel[role="muted"], QLabel#muted {{ color: {t["muted"]}; }}
QLabel[role="warning"] {{ color: {t["warn_ink"]}; }}
QLabel[role="error"] {{ color: {t["err_ink"]}; }}
QLabel[role="success"] {{ color: {t["ok"]}; font-weight: 600; }}
QLabel[role="banner"] {{
  background: {t["warn_bg"]};
  color: {t["warn_ink"]};
  border: 1px solid rgba(241, 182, 92, 0.35);
  border-radius: {t["radius_sm"]};
  padding: 12px 14px;
}}

QGroupBox {{
  font-weight: 600;
  border: 1px solid {t["border"]};
  border-radius: 24px;
  margin-top: 14px;
  padding-top: 12px;
  background: {t["surface"]};
  color: {t["ink"]};
}}
QGroupBox::title {{
  subcontrol-origin: margin;
  left: 12px;
  padding: 0 6px;
  color: {t["iris"]};
}}

QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit, QTableWidget, QListWidget {{
  background: {t["elev"]};
  border: 1px solid {t["border"]};
  border-radius: {t["radius_sm"]};
  padding: 8px 10px;
  color: {t["ink"]};
  selection-background-color: {t["accent"]};
  selection-color: {t["primary_ink"]};
}}
QComboBox QAbstractItemView {{
  background: {t["surface_solid"]};
  color: {t["ink"]};
  border: 1px solid {t["border"]};
  selection-background-color: {t["accent_soft"]};
  selection-color: {t["nav_active_ink"]};
}}
QLineEdit#search {{
  padding: 12px 16px;
  font-size: 14px;
  background: {t["elev"]};
  border-radius: 18px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus,
QTableWidget:focus, QListWidget:focus, QLineEdit#search:focus {{
  border: 2px solid {t["iris"]};
}}

QListWidget#albumGrid {{
  background: transparent;
  border: none;
  outline: none;
  padding: 4px;
}}
QListWidget#albumGrid::item {{
  background: {t["elev"]};
  border: 1px solid {t["border"]};
  border-radius: 20px;
  padding: 8px;
  margin: 6px;
  color: {t["ink"]};
}}
QListWidget#albumGrid::item:selected {{
  border: 2px solid {t["accent"]};
  background: {t["accent_soft"]};
}}
QListWidget#albumGrid::item:hover {{
  background: rgba(255, 255, 255, 0.75);
}}

QListWidget#historyCards {{
  background: transparent;
  border: none;
  outline: none;
}}
QListWidget#historyCards::item {{
  margin: 0 0 12px 0;
  padding: 0;
  border: none;
  background: transparent;
}}
QListWidget#historyCards::item:selected {{
  background: transparent;
}}

QListWidget#progressSteps {{
  background: transparent;
  border: none;
  outline: none;
}}
QListWidget#progressSteps::item {{
  padding: 10px 12px;
  border-radius: 14px;
  color: {t["muted"]};
}}
QListWidget#progressSteps::item:selected {{
  background: {t["accent_soft"]};
  color: {t["nav_active_ink"]};
  font-weight: 600;
}}

QProgressBar {{
  border: none;
  border-radius: 8px;
  text-align: center;
  min-height: 10px;
  background: rgba(45, 52, 70, 0.08);
  color: {t["muted"]};
}}
QProgressBar::chunk {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 {t["accent"]}, stop:1 {t["jade"]});
  border-radius: 8px;
}}

QRadioButton, QCheckBox {{
  spacing: 8px;
  min-height: 22px;
  color: {t["ink"]};
}}
QRadioButton:focus, QCheckBox:focus {{
  outline: 2px solid {t["iris"]};
}}

QLabel#coverPlaceholder {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 {t["rose"]}, stop:0.45 {t["iris"]}, stop:1 {t["accent"]});
  border-radius: 18px;
  color: {t["surface_solid"]};
  font-size: 13px;
  font-weight: 600;
}}

QScrollArea {{
  background: transparent;
  border: none;
}}
QScrollArea > QWidget > QWidget {{
  background: transparent;
}}

QHeaderView::section {{
  background: {t["elev_solid"]};
  color: {t["muted"]};
  border: none;
  border-bottom: 1px solid {t["border"]};
  padding: 6px 8px;
}}
QTableWidget {{
  gridline-color: {t["border"]};
}}
QToolTip {{
  background: {t["elev_solid"]};
  color: {t["ink"]};
  border: 1px solid {t["border"]};
  padding: 6px 8px;
}}
"""


APP_STYLE = ""


def apply_app_style(app: QApplication) -> None:
    """Fusion + polices OFL + QSS Brume pastel AVM-08E."""
    global APP_STYLE
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QStyleFactory

    load_embedded_fonts()
    APP_STYLE = _build_app_style()

    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        app.setStyle(fusion)
    else:
        app.setStyle("Fusion")

    pal = QPalette()
    mist = QColor(TOKEN["bg_mist"])
    surface = QColor(TOKEN["surface_solid"])
    ink = QColor(TOKEN["ink"])
    muted = QColor(TOKEN["muted"])
    accent = QColor(TOKEN["accent"])
    elev = QColor(TOKEN["elev_solid"])
    pal.setColor(QPalette.ColorRole.Window, mist)
    pal.setColor(QPalette.ColorRole.WindowText, ink)
    pal.setColor(QPalette.ColorRole.Base, elev)
    pal.setColor(QPalette.ColorRole.AlternateBase, surface)
    pal.setColor(QPalette.ColorRole.Text, ink)
    pal.setColor(QPalette.ColorRole.Button, elev)
    pal.setColor(QPalette.ColorRole.ButtonText, ink)
    pal.setColor(QPalette.ColorRole.Highlight, accent)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(TOKEN["primary_ink"]))
    pal.setColor(QPalette.ColorRole.ToolTipBase, elev)
    pal.setColor(QPalette.ColorRole.ToolTipText, ink)
    pal.setColor(QPalette.ColorRole.PlaceholderText, muted)
    pal.setColor(QPalette.ColorRole.BrightText, accent)
    app.setPalette(pal)
    app.setStyleSheet(APP_STYLE)
