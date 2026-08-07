import urllib.parse
from datetime import datetime

def generate_whatsapp_link(phone, message):
    """
    Generate WhatsApp click-to-chat link.
    Auto-prefixes +65 if missing for Singapore numbers.
    """
    clean_phone = str(phone).strip().replace(" ", "").replace("-", "").lstrip("+")
    
    # Auto-add 65 for Singapore 8-digit numbers
    if not clean_phone.startswith('65') and len(clean_phone) == 8:
        clean_phone = '65' + clean_phone
    
    encoded_msg = urllib.parse.quote(message, safe='')
    return f"https://wa.me/{clean_phone}?text={encoded_msg}"

def generate_reminder_message(session, resident_name, rsvp_url):
    """Generate personalized reminder message for a resident."""
    activity = session.get('activity_name', 'Community Event')
    date = session.get('session_date', 'TBA')
    time = session.get('session_time', 'TBA')
    location = session.get('location', 'Woodlands Zone 6')
    
    return (
        f"🌳 *Woodlands Zone 6 Community Hub*\n\n"
        f" *{activity}*\n"
        f"🗓️ Date: {date}\n"
        f"🕐 Time: {time}\n"
        f" Location: {location}\n\n"
        f"Hi {resident_name}! Please confirm your attendance:\n"
        f"{rsvp_url}\n\n"
        f"Tap the link above to RSVP! 👆"
    )

def generate_bulk_reminder_message(session, rsvp_url):
    """Generate a generic message for broadcasting to groups."""
    activity = session.get('activity_name', 'Community Event')
    date = session.get('session_date', 'TBA')
    time = session.get('session_time', 'TBA')
    location = session.get('location', 'Woodlands Zone 6')
    
    return (
        f"🌳 *Woodlands Zone 6 Community Hub*\n\n"
        f" *{activity}*\n"
        f"🗓️ Date: {date}\n"
        f"🕐 Time: {time}\n"
        f"📍 Location: {location}\n\n"
        f"Please confirm your attendance:\n"
        f"{rsvp_url}\n\n"
        f"Tap the link above to RSVP! 👆"
    )