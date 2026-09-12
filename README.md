# ProcureLens

ProcureLens is a hackathon prototype for **explainable public-procurement anomaly detection**. It helps human investigators identify procurement cases that deserve further review by surfacing unusual patterns in tender, bid, vendor, and contract data, explaining *why* each case was flagged, and showing the relationships between vendors that a plain spreadsheet would hide.

## Problem

Public procurement data is large, relational, and hard to audit manually. Irregularities such as unusually high award prices, suspiciously low competition, brand-new vendors winning large contracts, or vendors quietly sharing registration details with each other are easy to miss when reviewing tenders one at a time. ProcureLens turns raw tender/bid/vendor/contract records into a ranked, explainable review queue so a human reviewer can focus attention where it's most warranted.

**Important:** ProcureLens identifies *review candidates* based on statistical and rule-based signals. It does **not** declare fraud, corruption, or any wrongdoing. A high score means "this case may deserve a closer look," never a finding of guilt.

## Main Features

- A ranked list of tenders with a 0–100 review-priority score and a plain-language explanation for every score
- Sidebar filtering by department, tender category, review priority, procurement method, and minimum score
- A tender detail view: bids, the winning bid clearly identified, vendor history, and a signal-by-signal score breakdown
- A relationship-analysis panel showing whether the winning vendor shares a registered address or contact group with other vendors
- A recommended next action (e.g. "Prioritize for human review") derived from the review priority
- Downloadable CSV export of the currently filtered results
- A built-in "How scoring works" explanation and a synthetic-data evaluation panel comparing scores against deliberately planted test patterns
- A clearly labeled synthetic-data disclaimer throughout the interface

## Detection Signals

Every tender is scored using five transparent, rule-based signals computed only from observed procurement data (never from evaluation-only labels):

| Signal | Points | Rule |
|---|---|---|
| High price | 30 | Contract amount is more than ~1.25x the tender's estimated value |
| New vendor | 20 | Winning vendor was registered within 2 years of the tender date |
| Shared vendor relationship | 20 | Winning vendor shares a registered address or contact group with another vendor |
| Low competition | 15 | Tender received exactly 2 bids |
| Unusual bid pattern | 15 | Two or more competing bids fall within 0.3% of each other |

Scores map to a review priority: **Low** (0–24), **Medium** (25–49), **High** (50–74), **Critical** (75–100).

## Technology Stack

- **Python** for data generation, validation, and scoring
- **pandas** / **NumPy** for data processing
- **Streamlit** for the interactive dashboard
- **Altair** for in-dashboard charts
- Plain **CSV files** as the data layer — no database

## Project Structure

```text
ProcureLens/
├── data/
│   ├── raw/                  # Generated dataset used by scoring and the dashboard
│   │   ├── vendors.csv
│   │   ├── tenders.csv
│   │   ├── bids.csv
│   │   └── contracts.csv
│   └── evaluation/
│       ├── ground_truth.csv      # Evaluation-only labels; never read by scoring.py
│       └── scoring_results.csv   # Output of backend/app/scoring.py
├── scripts/
│   ├── config.py              # All dataset constants (sizes, seed, thresholds)
│   ├── generate_dataset.py    # Generates vendors, tenders, bids, contracts
│   ├── plant_patterns.py      # Plants ~75 synthetic review-candidate patterns
│   └── validate_dataset.py    # Validation checks for every generated file
├── backend/
│   ├── app/
│   │   └── scoring.py         # Explainable scoring logic (reads data/raw/ only)
│   └── requirements.txt
├── frontend/
│   ├── app.py                 # Streamlit dashboard
│   └── requirements.txt
├── docs/                      # Reserved for further documentation
├── tests/                     # Reserved for automated tests
├── requirements.txt           # Combined dependencies for the whole project
├── README.md
├── CLAUDE.md                  # Development instructions used to build this project
└── .gitignore
```

## Setup

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate      # On Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Generate the synthetic dataset

```bash
cd scripts
python generate_dataset.py
python plant_patterns.py
python validate_dataset.py
cd ..
```

### 4. Run the scoring pipeline

```bash
python backend/app/scoring.py
```

### 5. Run the dashboard

```bash
streamlit run frontend/app.py
```

Run this from the project root. The dashboard opens at `http://localhost:8501`.

## Synthetic Data Notice

All vendors, tenders, bids, contracts, and amounts in this project are **synthetically generated** with a fixed random seed for reproducibility. No real organizations, individuals, or procurement records are represented. `data/evaluation/ground_truth.csv` records which cases were deliberately planted for evaluation purposes only and is never used by the scoring logic in `backend/app/scoring.py`.

## A Note on Language

ProcureLens surfaces **review candidates** based on statistical and relationship signals. It does not, and cannot, determine that fraud, corruption, or any other wrongdoing has occurred. All results should be treated as a starting point for further human review, not a conclusion.
