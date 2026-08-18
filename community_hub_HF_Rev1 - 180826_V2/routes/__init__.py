# routes/__init__.py
"""Route handlers for URL modes"""

from .auto_checkin import handle_auto_checkin
from .legacy_checkin import handle_legacy_checkin
from .volunteer_mode import handle_volunteer_mode
from .volunteer_portal_mode import handle_volunteer_portal_mode
from .register_mode import handle_register_mode
from .rsvp_mode import handle_rsvp_mode