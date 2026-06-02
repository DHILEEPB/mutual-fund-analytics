# MutualFund Analytics — Day 1: Data Ingestion

> **Capstone Project | Data Engineering Track**
> Bluestock Fintech · June 2026

---

## 📌 Project Overview

This repository is the foundation of a **end-to-end Mutual Fund Analytics pipeline**. Day 1 focuses on **raw data ingestion and quality assurance** — fetching live NAV histories from the public AMFI/mfapi API, storing them as structured CSV files, and running a comprehensive data-quality audit before any analysis begins.

Key goals for Day 1:
| # | Goal |
|---|------|
| 1 | Establish a clean, reproducible project structure |
| 2 | Fetch and persist NAV history for 6 large-cap / blue-chip funds |
| 3 | Audit every raw CSV for shape, dtypes, missing values, and duplicates |
| 4 | Validate the fund master catalogue (if available) |
| 5 | Generate a consolidated data-quality report |

---

## 📂 Folder Structure

```
MutualFund-Analytics/
├── data/
│   ├── raw/                  ← Auto-populated by live_nav_fetch.py
│   │   ├── HDFC_Top100_nav.csv
│   │   ├── SBI_Bluechip_nav.csv
│   │   ├── ICICI_Bluechip_nav.csv
│   │   ├── Nippon_LargeCap_nav.csv
│   │   ├── Axis_Bluechip_nav.csv
│   │   ├── Kotak_Bluechip_nav.csv
│   │   └── fund_master.csv   ← (optional — place manually)
│   └── processed/            ← Cleaned/transformed outputs (Day 2+)
├── notebooks/                ← Jupyter EDA notebooks (Day 3+)
├── sql/                      ← SQL schema & queries (Day 2+)
├── dashboard/                ← Plotly/Dash dashboard (Day 4+)
├── reports/                  ← Auto-generated data-quality reports
├── data_ingestion.py         ← Quality audit script
├── live_nav_fetch.py         ← NAV fetcher script
├── requirements.txt          ← Python dependencies
├── README.md                 ← This file
└── .gitignore
```

---

## ⚙️ Setup Instructions

### Prerequisites
- Python **3.10 or later** (uses `X | Y` union type hints)
- Internet access (to reach `api.mfapi.in`)
- Git

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd MutualFund-Analytics
```

### 2. Create & activate a virtual environment *(recommended)*
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

---

## 🚀 How to Run the Scripts

All commands must be executed **from the project root** (`MutualFund-Analytics/`).

### Step 1 — Fetch live NAV data
```bash
python live_nav_fetch.py
```
Downloads NAV history for all 6 schemes and saves individual CSV files to `data/raw/`.

### Step 2 — Run the data-quality audit
```bash
python data_ingestion.py
```
Scans every CSV in `data/raw/`, prints a per-file report, optionally validates `fund_master.csv`, and prints a consolidated quality summary.  
A summary is also written to `reports/data_quality_report.txt`.

### Step 3 *(optional)* — Launch Jupyter Notebooks
```bash
jupyter notebook notebooks/
```

---

## 🌐 Data Sources

| Source | URL | Description |
|--------|-----|-------------|
| mfapi.in | `https://api.mfapi.in/mf/<scheme_code>` | Free, unofficial AMFI NAV API. Returns full NAV history in JSON. |
| AMFI India | `https://www.amfiindia.com/` | Official source for AMFI scheme codes |

### Schemes ingested (Day 1)

| Scheme Name | AMFI Code | Fund House |
|-------------|-----------|------------|
| HDFC Top 100 | 125497 | HDFC AMC |
| SBI Bluechip | 119551 | SBI Funds Management |
| ICICI Pru Bluechip | 120503 | ICICI Prudential AMC |
| Nippon India Large Cap | 118632 | Nippon India AMC |
| Axis Bluechip | 119092 | Axis AMC |
| Kotak Bluechip | 120841 | Kotak Mahindra AMC |

---

## 📦 Deliverables (Day 1)

- [x] `requirements.txt` — pinned project dependencies
- [x] `.gitignore` — standard Python ignore rules
- [x] `live_nav_fetch.py` — fetches NAV history from mfapi.in
- [x] `data/raw/*.csv` — one CSV per fund scheme
- [x] `data_ingestion.py` — data-quality audit pipeline
- [x] `reports/data_quality_report.txt` *(generated on first run)*
- [x] `README.md` — this document

---

## 🗺️ Roadmap

| Day | Focus |
|-----|-------|
| **1** | ✅ Data ingestion & quality audit |
| 2 | SQL schema design & data loading |
| 3 | Exploratory Data Analysis (EDA) with Jupyter |
| 4 | Return & risk metrics computation |
| 5 | Interactive Plotly/Dash dashboard |
| 6 | Automated reporting pipeline |
| 7 | Final presentation & documentation |

---

