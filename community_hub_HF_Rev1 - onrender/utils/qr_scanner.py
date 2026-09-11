"""Real-time QR code scanner component using html5-qrcode library"""
import streamlit.components.v1 as components
import streamlit as st

def qr_code_scanner_auto_detect(key="qr_scanner"):
    """
    Real-time QR code scanner with auto-detection using html5-qrcode library.
    Renders a live camera feed that automatically detects QR codes and injects the result into a Streamlit text input.
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
    let html5QrcodeScanner = null;

    function onScanSuccess(decodedText, decodedResult) {{
        // Prevent duplicate scans within 3 seconds
        if (decodedText !== lastScannedCode) {{
            lastScannedCode = decodedText;
            console.log("QR Code detected:", decodedText);
            
            // --- STREAMLIT INTEGRATION ---
            // Access the parent window (the main Streamlit app)
            const parentDoc = window.parent.document;
            // Find the specific text input by partial placeholder match (much more robust!)
            const targetInput = parentDoc.querySelector('input[placeholder*="Waiting for scan"]');
            
            if (targetInput) {{
                // Use the native setter to bypass React's controlled input restrictions
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeInputValueSetter.call(targetInput, decodedText);
                
                // Dispatch events to trigger Streamlit/React update
                targetInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                targetInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                
                console.log("Successfully injected QR code into Streamlit input.");
            }} else {{
                console.log("Could not find Streamlit input with placeholder containing 'Waiting for scan'");
            }}
            // -----------------------------

            // Pause scanning briefly to prevent rapid-fire duplicates
            if (html5QrcodeScanner) {{
                html5QrcodeScanner.pause();
                setTimeout(() => {{
                    html5QrcodeScanner.resume();
                    // Reset after 3 seconds to allow scanning the same code again if needed
                    setTimeout(() => {{ lastScannedCode = null; }}, 3000);
                }}, 1000);
            }}
        }}
    }}
    
    function onScanFailure(error) {{
        // Scan failed - ignore, keep scanning
    }}
    
    // Initialize scanner
    html5QrcodeScanner = new Html5QrcodeScanner(
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