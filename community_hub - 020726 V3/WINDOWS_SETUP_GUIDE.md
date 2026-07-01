# Windows Batch Launcher Setup Guide

## What You Get

Instead of a true .exe (which isn't possible with Streamlit), you get one-click batch files that handle everything automatically:

| File | Purpose | When to Use |
|------|---------|-------------|
| START_APP.bat | Full launcher with auto-setup | Main file - double-click this |
| QUICK_START.bat | Fast launch (no checks) | After first successful run |
| SETUP.bat | Install dependencies only | If you need to reinstall packages |
| CREATE_DESKTOP_SHORTCUT.vbs | Creates desktop shortcut | Run once to add to desktop |

---

## Folder Structure (After Setup)

community_hub/
  START_APP.bat              <- Double-click this to run
  QUICK_START.bat
  SETUP.bat
  CREATE_DESKTOP_SHORTCUT.vbs
  app.py
  config.py
  utils.py
  tab_checkin.py
  tab_qr_links.py
  tab_reports.py
  tab_manage.py
  tab_import.py
  tab_garden.py
  tab_residents.py
  requirements.txt
  README.md
  venv/                      <- Auto-created on first run
    Scripts/
    Lib/
    ...

---

## How to Use

### Method 1: Double-Click START_APP.bat (Recommended)

1. Copy all files to a folder (e.g., C:\CommunityHub\)
2. Double-click START_APP.bat
3. The script will:
   - Check Python is installed
   - Create virtual environment (first time only)
   - Install all packages (first time only, ~2-3 min)
   - Launch Streamlit in your browser

### Method 2: Desktop Shortcut

1. Double-click CREATE_DESKTOP_SHORTCUT.vbs
2. A shortcut appears on your desktop
3. Double-click the shortcut anytime to launch

### Method 3: Pin to Taskbar

1. Right-click START_APP.bat -> Create shortcut
2. Right-click the shortcut -> Properties
3. Click Change Icon -> Pick an icon
4. Right-click shortcut -> Pin to taskbar

---

## What Happens on First Run

[OK] Python detected. Python 3.11.4
[INFO] Creating virtual environment...
[OK] Virtual environment created.
[INFO] Checking dependencies...
[INFO] Installing dependencies (first run may take 2-3 minutes)...
    Collecting streamlit==1.40.0
    Collecting supabase==2.15.0
    ...
[OK] Dependencies installed.
==========================================
  LAUNCHING STREAMLIT APP...
  Browser will open automatically
  Press Ctrl+C to stop the server
==========================================

  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.1.100:8501

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Python is not installed" | Install Python 3.9+ from python.org. Check "Add Python to PATH" during install. |
| "pip is not recognized" | Reinstall Python and check "Add to PATH" |
| App won't open in browser | Manually go to http://localhost:8501 |
| "Port 8501 is in use" | Close other Streamlit apps, or edit batch to add --server.port 8502 |
| Dependencies fail to install | Run SETUP.bat as Administrator |
| Antivirus blocks batch file | Add folder to antivirus exclusion list |

---

## Making It Look More Like an App

### Option A: Custom Icon for Batch File
1. Create a shortcut to START_APP.bat
2. Right-click -> Properties -> Shortcut tab
3. Click Change Icon -> Browse to .ico file
4. Download a free icon from iconarchive.com

### Option B: Auto-Hide Command Window
To hide the black command window, create a new batch file called START_HIDDEN.bat:

    @echo off
    start /min START_APP.bat

Or use the VBScript shortcut which already handles this.

---

## Updating the App

When you get new code files:

1. Replace the .py files in the folder
2. Double-click START_APP.bat - it will auto-detect and reinstall if needed

Or manually update:
    call venv\Scripts\activate.bat
    pip install -r requirements.txt --upgrade
    streamlit run app.py

---

## Alternative: True Standalone with PyInstaller (Advanced)

If you absolutely need a single .exe file, you can use PyInstaller, but it has limitations:

    :: Install pyinstaller
    call venv\Scripts\activate.bat
    pip install pyinstaller

    :: Create exe (NOT recommended for Streamlit)
    pyinstaller --onefile --windowed app.py

Warning: PyInstaller with Streamlit is NOT recommended because:
- File size becomes 200+ MB
- Browser still required
- Supabase connection issues common
- Much harder to update

The batch file approach is the standard and most reliable method for Streamlit apps.

---

## Quick Reference Card

+-----------------------------------------+
|  USER ACTION -> RESULT                  |
+-----------------------------------------+
|  Double-click START_APP.bat             |
|    -> Auto-setup -> Open browser        |
|                                         |
|  Double-click QUICK_START.bat           |
|    -> Skip checks -> Faster launch      |
|                                         |
|  Double-click SETUP.bat                 |
|    -> Install only -> Don't run         |
|                                         |
|  Double-click CREATE_DESKTOP_SHORTCUT   |
|    -> Desktop icon created              |
|                                         |
|  Press Ctrl+C in window                 |
|    -> Stop server -> Close browser tab  |
+-----------------------------------------+

---

## Pro Tips

1. Pin to Start Menu: Right-click START_APP.bat -> Pin to Start
2. Auto-start on Windows boot: Place shortcut in shell:startup folder
3. Run on another PC: Just copy the entire folder - no install needed (Python required)
4. Backup: Zip the whole folder - includes all data via Supabase cloud

---

Questions? Check the main README.md or contact your system administrator.
