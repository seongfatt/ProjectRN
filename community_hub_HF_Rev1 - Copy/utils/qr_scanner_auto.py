import streamlit.components.v1 as components
from pathlib import Path

_COMPONENT_PATH = Path(__file__).resolve().parent / "qr_scanner_auto_ui"
_HTML_FILE = _COMPONENT_PATH / "index.html"

_component_ready = _HTML_FILE.exists()

if not _component_ready:
    print(f"❌ qr_scanner_auto NOT READY")
    print(f"   Looking for: {_HTML_FILE}")
    print(f"   Folder exists: {_COMPONENT_PATH.exists()}")
    _qr_scanner_auto = None
else:
    print(f"✅ qr_scanner_auto READY at {_COMPONENT_PATH}")
    _qr_scanner_auto = components.declare_component(
        "qr_scanner_auto",
        path=str(_COMPONENT_PATH),
    )


def qr_scanner_auto(height: int = 560, key: str = None):
    if _qr_scanner_auto is None:
        return None
    return _qr_scanner_auto(height=height, key=key, default=None)


def is_qr_scanner_auto_ready() -> bool:
    return _component_ready