"""
data_ingestion.py
=================
Day 1 - MutualFund Analytics | Data Ingestion & Quality Inspector
------------------------------------------------------------------
Reads every CSV file found in data/raw/, performs a thorough
exploratory data-quality audit on each file, and consolidates
all findings into a single summary report printed to the console
and optionally saved to reports/data_quality_report.txt.

Features
--------
* Auto-discovers all *.csv files under data/raw/
* Per-file report:
    - Filename & shape
    - Column data-types
    - First 5 rows preview
    - Missing-value analysis (count + percentage)
    - Duplicate-row detection
* Fund Master validation (if fund_master.csv is present):
    - Unique fund houses / categories / sub-categories / risk grades
    - AMFI scheme-code format validation
    - Cross-check: does every scheme code have NAV history on disk?
* Consolidated data-quality summary across all files

Usage (from the project root):
    python data_ingestion.py

Dependencies:
    pip install pandas numpy
"""

import os
import sys
import glob
import logging
import re
from datetime import datetime

import pandas as pd
import numpy as np

# Ensure stdout uses UTF-8 on Windows terminals (avoids cp1252 UnicodeEncodeError)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RAW_DATA_DIR: str = os.path.join("data", "raw")
REPORTS_DIR: str = "reports"
FUND_MASTER_FILENAME: str = "fund_master.csv"
REPORT_OUTPUT: str = os.path.join(REPORTS_DIR, "data_quality_report.txt")

# Expected column names in fund_master.csv (adjust to your actual schema)
FUND_MASTER_SCHEME_CODE_COL: str = "scheme_code"   # column holding AMFI codes
FUND_MASTER_FUND_HOUSE_COL: str = "fund_house"
FUND_MASTER_CATEGORY_COL: str = "category"
FUND_MASTER_SUBCATEGORY_COL: str = "sub_category"
FUND_MASTER_RISK_COL: str = "risk_grade"

# AMFI scheme codes are 6-digit integers
AMFI_CODE_PATTERN: re.Pattern = re.compile(r"^\d{6}$")

# Separator used in printed section headers
SEPARATOR: str = "=" * 70
THIN_SEP: str = "-" * 70


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def section_header(title: str) -> str:
    """Return a formatted section header string."""
    return f"\n{SEPARATOR}\n  {title}\n{SEPARATOR}"


def ensure_reports_dir() -> None:
    """Create the reports/ directory if it does not exist."""
    os.makedirs(REPORTS_DIR, exist_ok=True)


def discover_csv_files(directory: str) -> list[str]:
    """
    Recursively find all CSV files under *directory*.

    Parameters
    ----------
    directory : str
        Root directory to search (e.g. 'data/raw').

    Returns
    -------
    list[str]
        Sorted list of absolute-style relative paths to CSV files.
    """
    pattern = os.path.join(directory, "**", "*.csv")
    files = sorted(glob.glob(pattern, recursive=True))
    return files


def load_csv(filepath: str) -> pd.DataFrame | None:
    """
    Safely load a CSV file into a DataFrame.

    Returns None and logs a warning if the file cannot be parsed.
    """
    try:
        df = pd.read_csv(filepath, low_memory=False)
        return df
    except Exception as exc:
        logger.warning("Could not read '%s': %s", filepath, exc)
        return None


# ---------------------------------------------------------------------------
# Per-file analysis functions
# ---------------------------------------------------------------------------

def report_basic_info(df: pd.DataFrame, filepath: str) -> dict:
    """
    Print and return basic information about a DataFrame.

    Returns a dict with keys: filename, rows, cols.
    """
    filename = os.path.basename(filepath)
    rows, cols = df.shape
    print(section_header(f"File: {filename}"))
    print(f"  Path   : {filepath}")
    print(f"  Shape  : {rows:,} rows  ×  {cols} columns")
    return {"filename": filename, "rows": rows, "cols": cols}


def report_dtypes(df: pd.DataFrame) -> None:
    """Print column names and their inferred data-types."""
    print(f"\n{'Column':<35} {'Dtype':<20} Non-Null Count")
    print(THIN_SEP)
    for col in df.columns:
        non_null = df[col].notna().sum()
        print(f"  {col:<33} {str(df[col].dtype):<20} {non_null:,}")


def report_head(df: pd.DataFrame, n: int = 5) -> None:
    """Print the first *n* rows of the DataFrame."""
    print(f"\n  First {n} rows:")
    print(df.head(n).to_string(index=True))


def report_missing_values(df: pd.DataFrame) -> dict:
    """
    Analyse and print missing-value statistics.

    Returns a dict mapping column name -> missing count for columns
    that have at least one missing value.
    """
    total_cells = df.shape[0] * df.shape[1]
    missing_per_col = df.isnull().sum()
    missing_cols = missing_per_col[missing_per_col > 0]

    print(f"\n  Missing Values  (total cells: {total_cells:,})")
    print(THIN_SEP)

    if missing_cols.empty:
        print("  [OK] No missing values detected.")
        return {}

    print(f"  {'Column':<35} {'Missing':<10} {'% Missing'}")
    print("  " + "-" * 55)
    for col, count in missing_cols.items():
        pct = count / df.shape[0] * 100
        print(f"  {col:<35} {count:<10,} {pct:.2f}%")

    return missing_cols.to_dict()


def report_duplicates(df: pd.DataFrame) -> int:
    """
    Detect and report duplicate rows.

    Returns the count of duplicate rows.
    """
    dup_count = df.duplicated().sum()
    print(f"\n  Duplicate Rows:")
    print(THIN_SEP)
    if dup_count == 0:
        print("  [OK] No duplicate rows detected.")
    else:
        pct = dup_count / len(df) * 100
        print(f"  [WARN] {dup_count:,} duplicate rows found ({pct:.2f}% of total).")
    return int(dup_count)


def report_numeric_summary(df: pd.DataFrame) -> None:
    """Print descriptive statistics for numeric columns."""
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.empty:
        return
    print(f"\n  Numeric Column Summary:")
    print(numeric_df.describe().round(4).to_string())


# ---------------------------------------------------------------------------
# Fund Master validation
# ---------------------------------------------------------------------------

def validate_amfi_code(code) -> bool:
    """Return True if *code* matches the 6-digit AMFI scheme-code format."""
    return bool(AMFI_CODE_PATTERN.match(str(code).strip()))


def report_fund_master(df: pd.DataFrame, all_csv_files: list[str]) -> None:
    """
    Perform domain-specific validation on fund_master.csv.

    Checks
    ------
    1. Unique fund houses
    2. Unique categories
    3. Unique sub-categories
    4. Unique risk grades
    5. AMFI scheme-code format validation
    6. Whether every scheme code has a corresponding NAV CSV on disk
    """
    print(section_header("Fund Master Validation"))

    # ----------------------------------------------------------------
    # 1. Unique fund houses
    # ----------------------------------------------------------------
    if FUND_MASTER_FUND_HOUSE_COL in df.columns:
        fund_houses = df[FUND_MASTER_FUND_HOUSE_COL].dropna().unique()
        print(f"\n  Fund Houses ({len(fund_houses)} unique):")
        for fh in sorted(fund_houses):
            print(f"    • {fh}")
    else:
        print(f"  [WARN] Column '{FUND_MASTER_FUND_HOUSE_COL}' not found.")

    # ----------------------------------------------------------------
    # 2. Unique categories
    # ----------------------------------------------------------------
    if FUND_MASTER_CATEGORY_COL in df.columns:
        categories = df[FUND_MASTER_CATEGORY_COL].dropna().unique()
        print(f"\n  Categories ({len(categories)} unique):")
        for cat in sorted(categories):
            print(f"    • {cat}")
    else:
        print(f"  [WARN] Column '{FUND_MASTER_CATEGORY_COL}' not found.")

    # ----------------------------------------------------------------
    # 3. Unique sub-categories
    # ----------------------------------------------------------------
    if FUND_MASTER_SUBCATEGORY_COL in df.columns:
        subcats = df[FUND_MASTER_SUBCATEGORY_COL].dropna().unique()
        print(f"\n  Sub-Categories ({len(subcats)} unique):")
        for sc in sorted(subcats):
            print(f"    • {sc}")
    else:
        print(f"  [WARN] Column '{FUND_MASTER_SUBCATEGORY_COL}' not found.")

    # ----------------------------------------------------------------
    # 4. Unique risk grades
    # ----------------------------------------------------------------
    if FUND_MASTER_RISK_COL in df.columns:
        risk_grades = df[FUND_MASTER_RISK_COL].dropna().unique()
        print(f"\n  Risk Grades ({len(risk_grades)} unique):")
        for rg in sorted(risk_grades):
            print(f"    • {rg}")
    else:
        print(f"  [WARN] Column '{FUND_MASTER_RISK_COL}' not found.")

    # ----------------------------------------------------------------
    # 5. AMFI scheme-code validation
    # ----------------------------------------------------------------
    if FUND_MASTER_SCHEME_CODE_COL in df.columns:
        codes = df[FUND_MASTER_SCHEME_CODE_COL].dropna()
        invalid_mask = ~codes.astype(str).str.strip().str.match(r"^\d{6}$")
        invalid_codes = codes[invalid_mask]

        print(f"\n  AMFI Scheme-Code Validation  ({len(codes)} codes checked):")
        if invalid_codes.empty:
            print("  [OK] All scheme codes match the 6-digit AMFI format.")
        else:
            print(f"  [ERR] {len(invalid_codes)} invalid code(s) found:")
            for code in invalid_codes.values:
                print(f"       - {code}")

        # ----------------------------------------------------------------
        # 6. Cross-check: does each scheme have a NAV CSV?
        # ----------------------------------------------------------------
        print(f"\n  NAV Coverage Check  (cross-referencing data/raw/ CSV files):")

        # Build a set of scheme codes extracted from existing NAV filenames
        # Convention: <SchemeName>_nav.csv  → the numeric code is inside the CSV
        nav_codes_on_disk: set[str] = set()
        for csv_path in all_csv_files:
            basename = os.path.basename(csv_path)
            if basename == FUND_MASTER_FILENAME:
                continue
            # Try to read the scheme_code column from each NAV file
            try:
                nav_df = pd.read_csv(csv_path, usecols=["scheme_code"], nrows=1)
                code_val = str(nav_df["scheme_code"].iloc[0]).strip()
                nav_codes_on_disk.add(code_val)
            except Exception:
                pass  # file may not have a scheme_code column — skip

        missing_nav: list = []
        for code in codes.astype(str).str.strip().values:
            if code not in nav_codes_on_disk:
                missing_nav.append(code)

        if not missing_nav:
            print("  [OK] Every scheme code has corresponding NAV data on disk.")
        else:
            print(f"  [WARN] {len(missing_nav)} scheme(s) have no NAV CSV on disk:")
            for code in missing_nav:
                print(f"       - {code}")
    else:
        print(f"  [WARN] Column '{FUND_MASTER_SCHEME_CODE_COL}' not found in fund_master.")


# ---------------------------------------------------------------------------
# Consolidated quality summary
# ---------------------------------------------------------------------------

def print_consolidated_summary(file_summaries: list[dict]) -> None:
    """
    Print a consolidated data-quality table across all ingested files.

    Parameters
    ----------
    file_summaries : list[dict]
        Each dict contains keys:
        filename, rows, cols, missing_cols, duplicates, status.
    """
    print(section_header("CONSOLIDATED DATA QUALITY SUMMARY"))
    print(
        f"  {'File':<35} {'Rows':>8} {'Cols':>5} "
        f"{'Missing Cols':>14} {'Duplicates':>12} {'Status'}"
    )
    print("  " + "-" * 85)

    for s in file_summaries:
        status_icon = "[OK]  " if s.get("status") == "OK" else "[WARN]"
        print(
            f"  {s['filename']:<35} "
            f"{s['rows']:>8,} "
            f"{s['cols']:>5} "
            f"{s['missing_cols']:>14} "
            f"{s['duplicates']:>12,} "
            f"  {status_icon}  {s['status']}"
        )

    print(SEPARATOR)
    total_rows = sum(s["rows"] for s in file_summaries)
    print(f"  Total files processed : {len(file_summaries)}")
    print(f"  Total rows ingested   : {total_rows:,}")
    print(
        f"  Generated at          : "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print(SEPARATOR + "\n")


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the full data-ingestion and quality-audit pipeline."""
    ensure_reports_dir()

    logger.info(SEPARATOR)
    logger.info("  MutualFund Analytics — Day 1: Data Ingestion & Quality Audit")
    logger.info(SEPARATOR)

    # ------------------------------------------------------------------
    # 1. Discover CSV files
    # ------------------------------------------------------------------
    csv_files = discover_csv_files(RAW_DATA_DIR)

    if not csv_files:
        logger.warning(
            "No CSV files found under '%s'. "
            "Run live_nav_fetch.py first to populate raw data.",
            RAW_DATA_DIR,
        )
        return

    logger.info("Discovered %d CSV file(s) in '%s'.", len(csv_files), RAW_DATA_DIR)

    # ------------------------------------------------------------------
    # 2. Audit each file
    # ------------------------------------------------------------------
    file_summaries: list[dict] = []
    fund_master_path: str | None = None

    for filepath in csv_files:
        basename = os.path.basename(filepath)

        # Defer fund_master.csv to after all NAV files are processed
        if basename == FUND_MASTER_FILENAME:
            fund_master_path = filepath
            continue

        df = load_csv(filepath)
        if df is None:
            file_summaries.append(
                {
                    "filename": basename,
                    "rows": 0,
                    "cols": 0,
                    "missing_cols": "N/A",
                    "duplicates": 0,
                    "status": "READ ERROR",
                }
            )
            continue

        # Basic info
        info = report_basic_info(df, filepath)

        # Dtypes
        print("\n  Column Data-Types:")
        report_dtypes(df)

        # Head
        report_head(df)

        # Missing values
        missing = report_missing_values(df)

        # Duplicates
        dups = report_duplicates(df)

        # Numeric summary
        report_numeric_summary(df)

        # Determine quality status
        status = "OK"
        if missing:
            status = f"MISSING VALUES ({len(missing)} cols)"
        if dups > 0:
            status = status + " | DUPLICATES" if status != "OK" else f"DUPLICATES ({dups})"

        file_summaries.append(
            {
                "filename": info["filename"],
                "rows": info["rows"],
                "cols": info["cols"],
                "missing_cols": len(missing),
                "duplicates": dups,
                "status": status,
            }
        )

    # ------------------------------------------------------------------
    # 3. Fund master validation (if present)
    # ------------------------------------------------------------------
    if fund_master_path:
        fm_df = load_csv(fund_master_path)
        if fm_df is not None:
            info = report_basic_info(fm_df, fund_master_path)
            print("\n  Column Data-Types:")
            report_dtypes(fm_df)
            report_head(fm_df)
            missing = report_missing_values(fm_df)
            dups = report_duplicates(fm_df)

            # Domain-specific validation
            report_fund_master(fm_df, csv_files)

            status = "OK"
            if missing:
                status = f"MISSING VALUES ({len(missing)} cols)"
            if dups > 0:
                status = status + " | DUPLICATES" if status != "OK" else f"DUPLICATES ({dups})"

            file_summaries.append(
                {
                    "filename": info["filename"],
                    "rows": info["rows"],
                    "cols": info["cols"],
                    "missing_cols": len(missing),
                    "duplicates": dups,
                    "status": status,
                }
            )
    else:
        print(
            f"\n  [INFO] fund_master.csv not found in {RAW_DATA_DIR}. "
            "Skipping fund-master validation.\n"
            "  Place a fund_master.csv with columns "
            f"[{FUND_MASTER_SCHEME_CODE_COL}, {FUND_MASTER_FUND_HOUSE_COL}, "
            f"{FUND_MASTER_CATEGORY_COL}, {FUND_MASTER_SUBCATEGORY_COL}, "
            f"{FUND_MASTER_RISK_COL}] in data/raw/ to enable this check."
        )

    # ------------------------------------------------------------------
    # 4. Consolidated summary
    # ------------------------------------------------------------------
    print_consolidated_summary(file_summaries)

    logger.info("Data ingestion audit complete.")


if __name__ == "__main__":
    main()
