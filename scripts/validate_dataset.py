"""Validation checks for generated ProcureLens datasets: vendors, tenders, bids, contracts, ground truth."""

import re
from pathlib import Path

import pandas as pd

from config import (
    NUM_VENDORS,
    NUM_TENDERS,
    VENDOR_CATEGORIES,
    VENDOR_CITIES,
    REGISTRATION_DATE_START,
    REGISTRATION_DATE_END,
    SHARED_GROUP_SIZE,
    DEPARTMENTS,
    TENDER_DATE_START,
    TENDER_DATE_END,
    PROCUREMENT_METHODS,
    MIN_BIDS_PER_TENDER,
    MAX_BIDS_PER_TENDER,
    PLANTED_PATTERN_RATIO,
)

DATA_RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
DATA_EVAL_DIR = Path(__file__).resolve().parent.parent / "data" / "evaluation"

VENDOR_ID_PATTERN = re.compile(r"^VEN\d{4}$")


def validate_vendors(vendors_df):
    """
    Run sanity checks on the vendors DataFrame.

    Raises an AssertionError with a clear message on the first failed check.
    Returns True if every check passes.
    """
    assert len(vendors_df) == NUM_VENDORS, \
        f"Expected {NUM_VENDORS} vendors, found {len(vendors_df)}"

    assert vendors_df["vendor_id"].is_unique, "vendor_id values must be unique"
    assert vendors_df["vendor_id"].apply(lambda v: bool(VENDOR_ID_PATTERN.match(v))).all(), \
        "vendor_id values must match pattern VENnnnn"

    assert vendors_df["vendor_name"].notna().all(), "vendor_name must not be null"
    assert vendors_df["vendor_name"].is_unique, "vendor_name values must be unique"

    assert vendors_df["vendor_category"].isin(VENDOR_CATEGORIES).all(), \
        "vendor_category contains a value outside the allowed list"

    assert vendors_df["registered_city"].isin(VENDOR_CITIES).all(), \
        "registered_city contains a value outside the allowed list"

    registration_dates = pd.to_datetime(vendors_df["registration_date"])
    start = pd.Timestamp(REGISTRATION_DATE_START)
    end = pd.Timestamp(REGISTRATION_DATE_END)
    assert registration_dates.between(start, end).all(), \
        f"registration_date must fall between {REGISTRATION_DATE_START} and {REGISTRATION_DATE_END}"

    for group_col in ["address_group_id", "contact_group_id"]:
        assert vendors_df[group_col].notna().all(), f"{group_col} must not be null"
        group_sizes = vendors_df.groupby(group_col).size()
        invalid_sizes = group_sizes[~group_sizes.isin([1, SHARED_GROUP_SIZE])]
        assert invalid_sizes.empty, (
            f"{group_col} groups must have size 1 or {SHARED_GROUP_SIZE}, "
            f"found invalid sizes: {invalid_sizes.to_dict()}"
        )

    return True


TENDER_ID_PATTERN = re.compile(r"^TEN\d{4}$")


def validate_tenders(tenders_df):
    """
    Run sanity checks on the tenders DataFrame.

    Raises an AssertionError with a clear message on the first failed check.
    Returns True if every check passes.
    """
    assert len(tenders_df) == NUM_TENDERS, \
        f"Expected {NUM_TENDERS} tenders, found {len(tenders_df)}"

    assert tenders_df["tender_id"].is_unique, "tender_id values must be unique"
    assert tenders_df["tender_id"].apply(lambda v: bool(TENDER_ID_PATTERN.match(v))).all(), \
        "tender_id values must match pattern TENnnnn"

    assert tenders_df["department"].isin(DEPARTMENTS).all(), \
        "department contains a value outside the allowed list"

    assert tenders_df["tender_category"].isin(VENDOR_CATEGORIES).all(), \
        "tender_category contains a value outside the allowed list"

    assert tenders_df["tender_title"].notna().all(), "tender_title must not be null"

    assert (tenders_df["estimated_value"] > 0).all(), "estimated_value must be positive"

    tender_dates = pd.to_datetime(tenders_df["tender_date"])
    deadlines = pd.to_datetime(tenders_df["submission_deadline"])
    start = pd.Timestamp(TENDER_DATE_START)
    end = pd.Timestamp(TENDER_DATE_END)
    assert tender_dates.between(start, end).all(), \
        f"tender_date must fall between {TENDER_DATE_START} and {TENDER_DATE_END}"
    assert (deadlines > tender_dates).all(), \
        "submission_deadline must be after tender_date for every tender"

    assert (tenders_df["contract_duration_days"] > 0).all(), \
        "contract_duration_days must be positive"

    assert tenders_df["procurement_method"].isin(PROCUREMENT_METHODS).all(), \
        "procurement_method contains a value outside the allowed list"

    assert tenders_df["location"].isin(VENDOR_CITIES).all(), \
        "location contains a value outside the allowed list"

    return True


BID_ID_PATTERN = re.compile(r"^BID\d{6}$")
CONTRACT_ID_PATTERN = re.compile(r"^CON\d{4}$")


def validate_bids(bids_df, vendors_df, tenders_df):
    """
    Run sanity checks on the bids DataFrame against the vendors and tenders it references.

    Raises an AssertionError with a clear message on the first failed check.
    Returns True if every check passes.
    """
    assert bids_df["bid_id"].is_unique, "bid_id values must be unique"
    assert bids_df["bid_id"].apply(lambda v: bool(BID_ID_PATTERN.match(v))).all(), \
        "bid_id values must match pattern BIDnnnnnn"

    tender_ids = set(tenders_df["tender_id"])
    vendor_ids = set(vendors_df["vendor_id"])
    assert set(bids_df["tender_id"]).issubset(tender_ids), \
        "bids.csv references a tender_id that does not exist in tenders.csv"
    assert set(bids_df["vendor_id"]).issubset(vendor_ids), \
        "bids.csv references a vendor_id that does not exist in vendors.csv"
    assert set(bids_df["tender_id"]) == tender_ids, \
        "every tender must be represented in bids.csv"

    bids_per_tender = bids_df.groupby("tender_id").size()
    assert bids_per_tender.between(MIN_BIDS_PER_TENDER, MAX_BIDS_PER_TENDER).all(), \
        f"each tender must have between {MIN_BIDS_PER_TENDER} and {MAX_BIDS_PER_TENDER} bids"

    assert not bids_df.duplicated(subset=["tender_id", "vendor_id"]).any(), \
        "a vendor must not submit more than one bid for the same tender"

    winners_per_tender = bids_df.groupby("tender_id")["is_winner"].sum()
    assert (winners_per_tender == 1).all(), "every tender must have exactly one winning bid"

    assert (bids_df["bid_amount"] > 0).all(), "bid_amount must be positive"

    merged = bids_df.merge(tenders_df[["tender_id", "tender_date", "submission_deadline"]], on="tender_id")
    submission_times = pd.to_datetime(merged["submission_time"])
    tender_dates = pd.to_datetime(merged["tender_date"])
    deadlines = pd.to_datetime(merged["submission_deadline"])
    assert (submission_times >= tender_dates).all(), \
        "submission_time must not be before the tender_date"
    assert (submission_times <= deadlines + pd.Timedelta(days=1)).all(), \
        "submission_time must be on or before the submission_deadline"

    return True


def validate_contracts(contracts_df, bids_df, tenders_df):
    """
    Run sanity checks on the contracts DataFrame against the bids and tenders it references.

    Raises an AssertionError with a clear message on the first failed check.
    Returns True if every check passes.
    """
    assert len(contracts_df) == NUM_TENDERS, \
        f"Expected {NUM_TENDERS} contracts, found {len(contracts_df)}"

    assert contracts_df["contract_id"].is_unique, "contract_id values must be unique"
    assert contracts_df["contract_id"].apply(lambda v: bool(CONTRACT_ID_PATTERN.match(v))).all(), \
        "contract_id values must match pattern CONnnnn"

    assert set(contracts_df["tender_id"]) == set(tenders_df["tender_id"]), \
        "every tender must have exactly one contract"
    assert contracts_df["tender_id"].is_unique, "a tender must not have more than one contract"

    winning_bids = bids_df[bids_df["is_winner"]].set_index("tender_id")
    contracts_indexed = contracts_df.set_index("tender_id")
    expected_vendor = winning_bids.loc[contracts_indexed.index, "vendor_id"]
    expected_amount = winning_bids.loc[contracts_indexed.index, "bid_amount"]
    assert (contracts_indexed["winning_vendor_id"].to_numpy() == expected_vendor.to_numpy()).all(), \
        "winning_vendor_id must match the tender's winning bid"
    assert (contracts_indexed["contract_amount"].to_numpy() == expected_amount.to_numpy()).all(), \
        "contract_amount must match the tender's winning bid amount"

    start_dates = pd.to_datetime(contracts_df["contract_start_date"])
    end_dates = pd.to_datetime(contracts_df["contract_end_date"])
    assert (end_dates > start_dates).all(), "contract_end_date must be after contract_start_date"

    return True


def validate_ground_truth(ground_truth_df, tenders_df):
    """
    Run sanity checks on the ground-truth labels file.

    Raises an AssertionError with a clear message on the first failed check.
    Returns True if every check passes.
    """
    assert set(ground_truth_df["tender_id"]) == set(tenders_df["tender_id"]), \
        "every tender must appear exactly once in ground_truth.csv"
    assert ground_truth_df["tender_id"].is_unique, "tender_id values in ground_truth.csv must be unique"

    planted = ground_truth_df[ground_truth_df["is_planted_anomaly"]]
    not_planted = ground_truth_df[~ground_truth_df["is_planted_anomaly"]]

    expected_planted = round(PLANTED_PATTERN_RATIO * NUM_TENDERS)
    tolerance = 15
    assert abs(len(planted) - expected_planted) <= tolerance, (
        f"expected roughly {expected_planted} planted tenders "
        f"(+/- {tolerance}), found {len(planted)}"
    )

    assert (planted["pattern_types"].str.len() > 0).all(), \
        "every planted tender must have a non-empty pattern_types value"
    assert (planted["pattern_description"].str.len() > 0).all(), \
        "every planted tender must have a non-empty pattern_description value"

    assert (not_planted["pattern_types"].fillna("").str.len() == 0).all(), \
        "non-planted tenders must not have a pattern_types value"

    return True


if __name__ == "__main__":
    vendors_path = DATA_RAW_DIR / "vendors.csv"
    vendors_df = pd.read_csv(vendors_path)
    validate_vendors(vendors_df)
    print(f"vendors.csv passed all validation checks ({len(vendors_df)} rows)")

    tenders_path = DATA_RAW_DIR / "tenders.csv"
    tenders_df = pd.read_csv(tenders_path)
    validate_tenders(tenders_df)
    print(f"tenders.csv passed all validation checks ({len(tenders_df)} rows)")

    bids_path = DATA_RAW_DIR / "bids.csv"
    bids_df = pd.read_csv(bids_path)
    validate_bids(bids_df, vendors_df, tenders_df)
    print(f"bids.csv passed all validation checks ({len(bids_df)} rows)")

    contracts_path = DATA_RAW_DIR / "contracts.csv"
    contracts_df = pd.read_csv(contracts_path)
    validate_contracts(contracts_df, bids_df, tenders_df)
    print(f"contracts.csv passed all validation checks ({len(contracts_df)} rows)")

    ground_truth_path = DATA_EVAL_DIR / "ground_truth.csv"
    ground_truth_df = pd.read_csv(ground_truth_path)
    validate_ground_truth(ground_truth_df, tenders_df)
    print(f"ground_truth.csv passed all validation checks ({len(ground_truth_df)} rows)")
