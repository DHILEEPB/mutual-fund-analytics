"""
live_nav_fetch.py
=================
Day 1 - MutualFund Analytics | Live NAV Fetcher
-------------------------------------------------
Fetches historical NAV data from the free mfapi.in REST API for a
pre-defined set of large-cap / blue-chip mutual fund schemes and saves
each scheme's NAV history as a separate CSV file inside data/raw/.

API endpoint pattern:
    GET https://api.mfapi.in/mf/<scheme_code>

Response structure:
    {
        "status": "SUCCESS",
        "meta": { "fund_house": "...", "scheme_type": "...", ... },
        "data": [
            {"date": "DD-MM-YYYY", "nav": "<float-string>"},
            ...
        ]
    }

Usage (from the project root):
    python live_nav_fetch.py

Dependencies:
    pip install requests pandas
"""

import os
import sys
import time
import logging
import requests
import pandas as pd

# Ensure stdout uses UTF-8 on Windows terminals (avoids cp1252 UnicodeEncodeError)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Logging configuration
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
BASE_URL: str = "https://api.mfapi.in/mf/{scheme_code}"
RAW_DATA_DIR: str = os.path.join("data", "raw")

# Mapping: friendly name -> AMFI scheme code
SCHEMES: dict[str, int] = {
    "HDFC_Top100": 125497,
    "SBI_Bluechip": 119551,
    "ICICI_Bluechip": 120503,
    "Nippon_LargeCap": 118632,
    "Axis_Bluechip": 119092,
    "Kotak_Bluechip": 120841,
}

# HTTP request settings
REQUEST_TIMEOUT: int = 30          # seconds before giving up on a single request
RETRY_DELAY: float = 2.0           # seconds to wait between retry attempts
MAX_RETRIES: int = 3               # maximum number of retries per scheme


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def ensure_directories() -> None:
    """Create data/raw/ directory tree if it does not already exist."""
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    logger.info("Output directory ready: %s", RAW_DATA_DIR)


def fetch_nav_data(scheme_code: int, scheme_name: str) -> pd.DataFrame | None:
    """
    Fetch NAV history for a single scheme from the mfapi.in API.

    Parameters
    ----------
    scheme_code : int
        AMFI scheme code (e.g. 125497 for HDFC Top 100).
    scheme_name : str
        Human-readable scheme label used in log messages.

    Returns
    -------
    pd.DataFrame | None
        DataFrame with columns [date, nav, fund_house, scheme_name,
        scheme_category, scheme_type, scheme_code] on success, or
        None if the request ultimately fails.
    """
    url = BASE_URL.format(scheme_code=scheme_code)
    logger.info("Fetching NAV for %-20s  (code: %s)", scheme_name, scheme_code)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()                  # raises HTTPError on 4xx/5xx
            payload = response.json()

            # ----------------------------------------------------------------
            # Validate API response structure
            # ----------------------------------------------------------------
            if payload.get("status") != "SUCCESS":
                logger.warning(
                    "API returned non-SUCCESS status for %s: %s",
                    scheme_name,
                    payload.get("status"),
                )
                return None

            raw_records: list[dict] = payload.get("data", [])
            meta: dict = payload.get("meta", {})

            if not raw_records:
                logger.warning("No NAV records returned for %s", scheme_name)
                return None

            # ----------------------------------------------------------------
            # Build DataFrame
            # ----------------------------------------------------------------
            df = pd.DataFrame(raw_records)   # columns: date, nav

            # Parse date — API sends DD-MM-YYYY
            df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")

            # NAV arrives as a string; coerce to float
            df["nav"] = pd.to_numeric(df["nav"], errors="coerce")

            # Enrich with metadata columns
            df["scheme_code"] = scheme_code
            df["scheme_name"] = scheme_name
            df["fund_house"] = meta.get("fund_house", "Unknown")
            df["scheme_category"] = meta.get("scheme_category", "Unknown")
            df["scheme_type"] = meta.get("scheme_type", "Unknown")

            # Sort chronologically (API returns newest-first by default)
            df.sort_values("date", inplace=True)
            df.reset_index(drop=True, inplace=True)

            logger.info(
                "  [OK] %s - %d NAV records  (%s -> %s)",
                scheme_name,
                len(df),
                df["date"].min().strftime("%d-%b-%Y"),
                df["date"].max().strftime("%d-%b-%Y"),
            )
            return df

        except requests.exceptions.Timeout:
            logger.warning(
                "  Attempt %d/%d timed out for %s. Retrying in %.1fs …",
                attempt, MAX_RETRIES, scheme_name, RETRY_DELAY,
            )
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "  Attempt %d/%d failed for %s: %s. Retrying in %.1fs …",
                attempt, MAX_RETRIES, scheme_name, exc, RETRY_DELAY,
            )

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    logger.error("All %d attempts failed for %s. Skipping.", MAX_RETRIES, scheme_name)
    return None


def save_to_csv(df: pd.DataFrame, scheme_name: str) -> str:
    """
    Persist a NAV DataFrame to a CSV file inside data/raw/.

    Parameters
    ----------
    df : pd.DataFrame
        NAV DataFrame to save.
    scheme_name : str
        Used to derive the output filename.

    Returns
    -------
    str
        Absolute path to the saved CSV file.
    """
    filename = f"{scheme_name}_nav.csv"
    filepath = os.path.join(RAW_DATA_DIR, filename)
    df.to_csv(filepath, index=False)
    logger.info("  [SAVED] -> %s  (%d rows)", filepath, len(df))
    return filepath


def print_summary(results: dict[str, str | None]) -> None:
    """Print a tabular ingestion summary at the end of the run."""
    print("\n" + "=" * 65)
    print("  INGESTION SUMMARY")
    print("=" * 65)
    print(f"  {'Scheme':<22} {'Status':<12} {'Output File'}")
    print("  " + "-" * 62)
    for name, path in results.items():
        if path:
            status = "[OK]     "
            output = os.path.basename(path)
        else:
            status = "[FAILED] "
            output = "-"
        print(f"  {name:<22} {status:<12} {output}")
    print("=" * 65 + "\n")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Orchestrate the full NAV fetch-and-save pipeline."""
    logger.info("=" * 60)
    logger.info("  MutualFund Analytics — Day 1: Live NAV Fetcher")
    logger.info("=" * 60)

    ensure_directories()

    results: dict[str, str | None] = {}

    for scheme_name, scheme_code in SCHEMES.items():
        df = fetch_nav_data(scheme_code, scheme_name)
        if df is not None:
            saved_path = save_to_csv(df, scheme_name)
            results[scheme_name] = saved_path
        else:
            results[scheme_name] = None
        # Polite delay between requests to avoid rate-limiting
        time.sleep(0.5)

    print_summary(results)

    success_count = sum(1 for v in results.values() if v is not None)
    logger.info(
        "Done. %d/%d schemes fetched successfully.",
        success_count,
        len(SCHEMES),
    )


if __name__ == "__main__":
    main()
