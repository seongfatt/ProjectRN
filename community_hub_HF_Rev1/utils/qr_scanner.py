"""Real-time QR code scanner component using html5-qrcode library"""
import streamlit.components.v1 as components
import streamlit as st

def qr_code_scanner_auto_detect(key="qr_scanner"):
    """
    Real-time QR code scanner with auto-detection using html5-qrcode library.
    Renders a live camera feed that automatically detects QR codes and injects the result into a Streamlit text input.
    Now includes a hidden trigger button to force Streamlit reactivity on JS-injected values.
    """
    st.markdown("""
    <style>
    #reader { width: 100%; max-width: 500px; margin: 0 auto; border-radius: 10px; }
    .scanner-container { text-align: center; padding: 20px; }
    </style>
    """, unsafe_allow_html=True)
    
    scanner_html = f"""
    <div class="scanner-container">
        <div id="reader"></div>
        <p style="color: #666; margin-top: 15px;">📷 Point camera at QR code - Auto-detection enabled</p>
    </div>

    <script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
    <script>
    let html5QrcodeScanner = null;

    function onScanSuccess(decodedText) {{
        console.log("QR scanned:", decodedText);
        // 🔥 Redirect to self with QR in query param (forces full reload)
        const url = new URL(window.location);
        url.searchParams.set('qr', decodedText);
        window.location.href = url.toString();
    }}

    function onScanFailure() {{}}

    html5QrcodeScanner = new Html5QrcodeScanner("reader", {{
        fps: 10,
        qrbox: {{ width: 250, height: 250 }},
        aspectRatio: 1.0,
        disableFlip: false
    }}, false);

    html5QrcodeScanner.render(onScanSuccess, onScanFailure);
    </script>
    """
    
    # Render the HTML component
    components.html(scanner_html, height=500)

def clear_scanned_qr():
    """Clear the scanned QR code from session state"""
    if 'scanned_qr_code' in st.session_state:
        st.session_state.scanned_qr_code = None