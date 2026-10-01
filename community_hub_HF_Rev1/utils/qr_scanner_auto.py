"""
Auto-firing QR scanner Streamlit component.
Handles BOTH camera scanning AND USB scanner input.

Returns: dict {value: str, ts: int} or None
"""
import streamlit.components.v1 as components
from pathlib import Path

_COMPONENT_PATH = Path(__file__).resolve().parent / "qr_scanner_auto_ui"

_qr_scanner_auto = components.declare_component(
    "qr_scanner_auto",
    path=str(_COMPONENT_PATH),
)


def qr_scanner_auto(height: int = 560, key: str = None):
    """Render the auto-firing QR scanner component."""
    return _qr_scanner_auto(height=height, key=key, default=None)