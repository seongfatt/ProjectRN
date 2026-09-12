"""Real-time QR code scanner component using html5-qrcode library"""
import streamlit.components.v1 as components
import streamlit as st

def qr_code_scanner_auto_detect(key="qr_scanner"):
    """
    Renders a live camera feed that automatically detects QR codes and sends the result to Streamlit
    using postMessage(), which is more reliable than DOM injection in modern Streamlit apps.
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
        // 🔥 Send QR to Streamlit via postMessage
        window.parent.postMessage({{ type: 'QR_SCAN', data: decodedText }}, '*');
        // Pause briefly to avoid rapid-fire scans
        html5QrcodeScanner.pause();
        setTimeout(() => {{
            html5QrcodeScanner.resume();
        }}, 1000);
    }}

    function onScanFailure(error) {{
        console.error("QR Scan Failed:", error);
        // Fallback: show user-friendly message
        const container = document.querySelector('.scanner-container');
        if (container) {{
            container.innerHTML += `<div style='color:#d32f2f; margin-top: 10px;'>⚠️ Camera access failed. Try 'Snapshot QR Scanner' instead.</div>`;
        }}
    }}

    function startScanner() {{
        try {{
            html5QrcodeScanner = new Html5QrcodeScanner("reader", {{
                fps: 10,
                qrbox: {{ width: 250, height: 250 }},
                aspectRatio: 1.0,
                disableFlip: false
            }}, false);

            html5QrcodeScanner.render(onScanSuccess, onScanFailure);
        }} catch (err) {{
            console.error("Scanner init failed:", err);
            const container = document.querySelector('.scanner-container');
            if (container) {{
                container.innerHTML = `<div style='color:#d32f2f; margin-top: 10px;'>❌ QR scanner failed to start. Try refreshing the page.</div>`;
            }}
        }}
    }}

    // Try starting the scanner after a small delay
    window.addEventListener('load', () => {{
        setTimeout(startScanner, 500);
    }});
    </script>
    """

    # Render the HTML component
    components.html(scanner_html, height=500)

def clear_scanned_qr():
    """Clear the scanned QR code from session state"""
    if 'scanned_qr_code' in st.session_state:
        st.session_state.scanned_qr_code = None