"""Real-time QR code scanner component using html5-qrcode library"""
import streamlit.components.v1 as components
import streamlit as st

def qr_code_scanner_auto_detect(key="qr_scanner"):
    """
    Real-time QR code scanner with auto-detection using html5-qrcode library.
    Renders a live camera feed that automatically detects QR codes.
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
    let lastScannedCode = null;
    
    function onScanSuccess(decodedText, decodedResult) {{
        // Prevent duplicate scans within 2 seconds
        if (decodedText !== lastScannedCode) {{
            lastScannedCode = decodedText;
            
            // Send to Streamlit via custom event
            const event = new CustomEvent('qr-scanned', {{
                detail: {{ qrData: decodedText }}
            }});
            document.dispatchEvent(event);
            
            // Pause scanning briefly
            if (typeof html5QrcodeScanner !== 'undefined') {{
                html5QrcodeScanner.pause();
                setTimeout(() => {{
                    html5QrcodeScanner.resume();
                    lastScannedCode = null;
                }}, 2000);
            }}
        }}
    }}
    
    function onScanFailure(error) {{
        // Scan failed - ignore, keep scanning
        console.warn(`QR scan error: ${{error}}`);
    }}
    
    // Initialize scanner
    let html5QrcodeScanner = new Html5QrcodeScanner(
        "reader",
        {{ 
            fps: 10,
            qrbox: {{ width: 250, height: 250 }},
            aspectRatio: 1.0,
            disableFlip: false
        }},
        /* verbose= */ false
    );
    
    html5QrcodeScanner.render(onScanSuccess, onScanFailure);
    </script>
    """
    
    # Render the HTML component
    components.html(scanner_html, height=500)

def clear_scanned_qr():
    """Clear the scanned QR code from session state"""
    if 'scanned_qr_code' in st.session_state:
        st.session_state.scanned_qr_code = None