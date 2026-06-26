# 🏘️ Woodlands Zone 6 - Community Hub

A unified Streamlit application for managing senior community activities, event attendance, and rooftop garden plot rentals — all connected to a single Supabase database.

---

## 📋 Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [Database Schema](#database-schema)
- [Installation](#installation)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [User Roles](#user-roles)
- [Usage Guide](#usage-guide)
- [Troubleshooting](#troubleshooting)

---

## ✨ Features

| Module | Description |
|--------|-------------|
| **📝 Check-In** | Mark attendance for any activity with custom session labels |
| **📱 QR/Links** | Generate QR codes and WhatsApp self-check-in links per resident |
| **📊 Reports** | Daily/weekly/monthly/yearly attendance reports with CSV/Excel export |
| **⚙️ Manage** | Register residents, create activities, convert New → Regular status |
| **📥 Import** | Bulk import attendance from WhatsApp poll text (fuzzy name matching) |
| **🌿 Garden** | Visual 76-plot grid, plot requests, admin approval, payment tracking |
| **👥 Residents** | Unified resident directory with entitlements and activity history |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────┐
│         Streamlit App (Hugging Face)    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ Admin   │  │ Checker │  │ Resident│ │
│  │ (7 tabs)│  │ (4 tabs)│  │ (QR/Link│ │
│  └────┬────┘  └────┬────┘  └────┬────┘ │
│       └─────────────┴─────────────┘     │
│                   │                      │
│              Supabase Client             │
└───────────────────┬─────────────────────┘
                    │
        ┌───────────┴───────────┐
        │    Supabase Database   │
        │  ┌─────────────────┐  │
        │  │ participants    │  │
        │  │ attendance      │  │
        │  │ garden_plots    │  │
        │  │ plot_requests   │  │
        │  │ activities  🆕  │  │
        │  └─────────────────┘  │
        └───────────────────────┘
```

---

## 🗄️ Database Schema

### `participants` (Existing — Keep As-Is)
| Column | Type | Description |
|--------|------|-------------|
| `id` | text | Unique resident ID |
| `name` | text | Full name (UPPERCASE) |
| `contact` | text | Phone number |
| `indemnity` | bool | Indemnity form signed |
| `is_new` | bool | New vs Regular status |
| `registration_date` | date | Join date |
| `active` | bool | Active/inactive |

### `attendance` (Existing — Keep As-Is)
| Column | Type | Description |
|--------|------|-------------|
| `id` | int8 | Auto-increment |
| `participant_id` | text | FK to participants |
| `name` | text | Resident name (denormalized) |
| `date` | date | Attendance date |
| `session_1` | bool | Session 1 attended |
| `session_2` | bool | Session 2 attended |
| `timestamp` | timestamptz | Record time |
| `self_checkin` | bool | Self-check-in flag |
| `source` | text | **Activity name** |

### `garden_plots` (Existing + Optional Column)
| Column | Type | Description |
|--------|------|-------------|
| `plot_number` | int4 | Plot ID (1-76) |
| `plot_type` | text | A/B/C/D |
| `area` | float8 | Plot area m² |
| `occupied` | bool | Taken/Available |
| `user_id` | text | Owner resident ID |
| `user_name` | text | Owner name |
| `contact` | text | Owner contact |
| `change_log` | text | Audit trail |
| `updated_at` | timestamp | Last update |
| `paid` | bool | **🆕 Payment status** *(optional)* |

### `plot_requests` (Existing — Keep As-Is)
| Column | Type | Description |
|--------|------|-------------|
| `id` | int4 | Request ID |
| `plot_number` | int4 | Requested plot |
| `user_id` | text | Requester ID |
| `user_name` | text | Requester name |
| `contact` | text | Contact info |
| `notes` | text | Additional notes |
| `status` | text | pending/approved/rejected |
| `created_at` | timestamp | Request time |

### `activities` 🆕 **NEW TABLE**
```sql
create table activities (
  id serial primary key,
  name text not null,
  session_1_label text default 'Session 1',
  session_2_label text default 'Session 2',
  active boolean default true
);
```

**Insert default activity:**
```sql
insert into activities (name, session_1_label, session_2_label) 
values ('Cardio Drumming', 'Session 1 (7PM-8PM)', 'Session 2 (8PM-9PM)');
```

---

## 📦 Installation

### Local Development

```bash
# 1. Clone or download files
git clone <your-repo> community_hub
cd community_hub

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scriptsctivate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run locally
streamlit run app.py
```

### Dependencies (`requirements.txt`)
```
streamlit>=1.28.0
supabase>=2.0.0
pandas>=2.0.0
python-dotenv>=1.0.0
qrcode>=7.4.0
Pillow>=10.0.0
openpyxl>=3.1.0
```

---

## ⚙️ Configuration

### Environment Variables (Optional)
Create a `.env` file or set in Hugging Face Space settings:

```bash
ADMIN_PASSWORD=your_admin_password      # Default: admin123
CHECKER_PASSWORD=your_checker_password  # Default: checker123
APP_URL=https://your-app.hf.space       # For QR/WhatsApp links
```

### Supabase Connection
Edit `config.py` if your Supabase credentials change:
```python
SUPABASE_URL = "https://nqmvsjubgsghjpzojaxm.supabase.co"
SUPABASE_KEY = "your-anon-key"
```

### Hugging Face Space Setup
1. Create new Space → Select **Streamlit** SDK
2. Upload all `.py` files and `requirements.txt`
3. Set environment variables in Space Settings → Secrets
4. Update `APP_URL` in `config.py` to your Space URL

---

## 🚀 Deployment

### Hugging Face Spaces (Recommended — Free)

```bash
# Install Hugging Face CLI
pip install huggingface-hub

# Login
huggingface-cli login

# Create repository
huggingface-cli repo create community-hub --type space --sdk streamlit

# Clone and push
git clone https://huggingface.co/spaces/YOUR_USERNAME/community-hub
cd community-hub
# Copy all files here
git add .
git commit -m "Initial commit"
git push
```

**App will be live at:** `https://YOUR_USERNAME-community-hub.hf.space`

### Self-Check-In URL Format
```
https://your-app.hf.space/?mode=checkin&pid=RESIDENT_ID&date=YYYYMMDD&tk=TOKEN&act=Activity%20Name
```

---

## 👥 User Roles

| Role | Access | Password |
|------|--------|----------|
| **Admin** | All 7 tabs: Check-In, QR/Links, Reports, Manage, Import, Garden, Residents | `ADMIN_PASSWORD` |
| **Checker** | 4 tabs: Check-In, QR/Links, Reports, Garden (view only) | `CHECKER_PASSWORD` |
| **Resident** | Self check-in via QR scan or WhatsApp link (no login needed) | N/A |

---

## 📖 Usage Guide

### For Admins

#### 1. Create a New Activity
- Go to **⚙️ Manage → 🎯 Activities**
- Click **Add New Activity**
- Enter name and session labels (e.g., "Yoga", "Morning", "Afternoon")
- The activity now appears in the sidebar selector

#### 2. Mark Attendance
- Select activity from sidebar
- Go to **📝 Check-In**
- Search resident or scroll list
- Check Session 1 and/or Session 2
- Auto-converts New → Regular after 3 attendances

#### 3. Generate QR Codes
- Go to **📱 QR/Links**
- Select activity, click **Generate**
- QR codes display for all active residents
- Download CSV for bulk WhatsApp sending
- Or use **Auto-Open All WhatsApp** (disable popup blocker)

#### 4. Manage Garden Plots
- Go to **🌿 Garden**
- View visual grid of all 76 plots
- Approve/reject pending requests in **🔐 Admin Panel**
- Direct assign or force release plots
- Track payment status in **👥 Residents**

#### 5. View Reports
- Go to **📊 Reports**
- Select period (Daily/Weekly/Monthly/Yearly/Custom)
- Filter by activity
- Export to CSV or Excel

#### 6. Import from WhatsApp Poll
- Go to **📥 Import**
- Paste names from WhatsApp poll into Session 1 / Session 2 boxes
- Click **Analyze & Match** (fuzzy matching)
- Review matches, confirm, then **Import to DB**

### For Residents (Self Check-In)

#### Via QR Code
1. Admin generates QR code for the resident
2. Resident scans QR with phone camera
3. Page opens → Tap session(s) → Confirm

#### Via WhatsApp Link
1. Admin sends WhatsApp message with personal link
2. Resident taps link
3. Page opens → Tap session(s) → Confirm

---

## 🔒 PDPA Compliance

- Phone numbers masked by default (show only last 4 digits: `••••1234`)
- Admin toggle in **👥 Residents** to view full numbers (resets on refresh)
- All exports include masked numbers unless admin explicitly toggles
- QR links use SHA-256 tokens with 1-day expiry

---

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| **Database not connected** | Check Supabase URL/key. Supabase free tier pauses after inactivity — refresh page to wake up |
| **QR codes not generating** | Ensure `qrcode` and `Pillow` are in `requirements.txt` |
| **WhatsApp links not working** | Update `APP_URL` in `config.py` to your actual deployed URL |
| **Attendance not showing in reports** | Check that `source` field matches activity name exactly |
| **Garden plot grid misaligned** | This is a responsive layout — works best on desktop or tablet |
| **Payment status not showing** | Add `paid` boolean column to `garden_plots` table, or code will skip gracefully |
| **Session state lost on refresh** | This is normal Streamlit behavior — data persists in Supabase |

---

## 📝 File Reference

| File | Purpose | Lines |
|------|---------|-------|
| `app.py` | Main entry: auth, self-check-in mode, tab routing | ~200 |
| `config.py` | Supabase config, activities, plot types, CSS | ~100 |
| `utils.py` | Shared helpers: mask_phone, DB CRUD, tokens | ~150 |
| `tab_checkin.py` | Activity-generic attendance marking | ~120 |
| `tab_qr_links.py` | QR generation + WhatsApp bulk send | ~100 |
| `tab_reports.py` | Multi-activity reports with export | ~120 |
| `tab_manage.py` | Participant + activity management | ~80 |
| `tab_import.py` | WhatsApp poll fuzzy import | ~120 |
| `tab_garden.py` | 76-plot grid + requests + admin | ~200 |
| `tab_residents.py` | Resident directory + entitlements | ~150 |

---

## 🔄 Migration from Old Systems

### From CardioDrum_Attendance
- ✅ `participants` table — **no changes**
- ✅ `attendance` table — **no changes** (adds `source` field automatically)
- ✅ All existing data preserved

### From Rooftopgarden
- ✅ `garden_plots` table — **no changes** (optional `paid` column)
- ✅ `plot_requests` table — **no changes**
- ✅ All existing data preserved

### New Requirements
- 🆕 Create `activities` table (see SQL above)
- 🆕 Install `qrcode` and `Pillow` packages
- 🆕 Set `APP_URL` environment variable

---

## 📧 Support

**Location:** Block 622 Woodlands Drive 52 #01-22  
**Issues:** Contact system administrator  
**Version:** 2.0 | **Last Updated:** June 2026

---

*Built with ❤️ for Woodlands Zone 6 Community*
