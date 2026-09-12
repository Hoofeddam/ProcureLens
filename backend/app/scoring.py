"""
Explainable anomaly-priority scoring for ProcureLens tenders.

Ranks tenders for human review using transparent, rule-based signals computed
only from observed procurement data (vendors, tenders, bids, contracts).
This module must never read data/evaluation/ground_truth.csv - that file is
for evaluation only and would leak the answer into the detector.

A high score means "this tender deserves a closer look", not "this tender
involves wrongdoing". Output uses neutral language throughout.
"""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_EVAL_DIR = PROJECT_ROOT / "data" / "evaluation"

# Signal thresholds
HIGH_PRICE_RATIO_THRESHOLD = 1.25
LOW_COMPETITION_BID_COUNT = 2
NEW_VENDOR_WINDOW_DAYS = 730
CLOSE_BID_RELATIVE_THRESHOLD = 0.003

# Signal weights (must sum to 100)
WEIGHT_HIGH_PRICE = 30
WEIGHT_LOW_COMPETITION = 15
WEIGHT_NEW_VENDOR = 20
WEIGHT_SHARED_RELATIONSHIP = 20
WEIGHT_UNUSUAL_BID_PATTERN = 15

REVIEW_CANDIDATE_MIN_SCORE = 25

VALID_REVIEW_PRIORITIES = ["Low", "Medium", "High", "Critical"]


def load_scoring_inputs():
    """Load only the observed procurement data. Ground truth is never loaded here."""
    vendors_df = pd.read_csv(DATA_RAW_DIR / "vendors.csv")
    tenders_df = pd.read_csv(DATA_RAW_DIR / "tenders.csv")
    bids_df = pd.read_csv(DATA_RAW_DIR / "bids.csv")
    contracts_df = pd.read_csv(DATA_RAW_DIR / "contracts.csv")
    return vendors_df, tenders_df, bids_df, contracts_df


def compute_high_price_signal(contract_amount, estimated_value):
    """Compare the contract amount with the estimated value. Returns (price_ratio, flag)."""
    if pd.isna(contract_amount) or pd.isna(estimated_value) or estimated_value <= 0:
        return None, False
    price_ratio = contract_amount / estimated_value
    return price_ratio, price_ratio > HIGH_PRICE_RATIO_THRESHOLD


def compute_low_competition_signal(bid_count):
    """Flag tenders that received the minimum realistic number of bids."""
    return bid_count == LOW_COMPETITION_BID_COUNT


def compute_new_vendor_signal(tender_date, registration_date):
    """Compute the winning vendor's age in days at the tender date. Returns (age_days, flag)."""
    if pd.isna(tender_date) or pd.isna(registration_date):
        return None, False
    vendor_age_days = (pd.Timestamp(tender_date) - pd.Timestamp(registration_date)).days
    is_new_vendor = 0 <= vendor_age_days <= NEW_VENDOR_WINDOW_DAYS
    return vendor_age_days, is_new_vendor


def compute_shared_relationship_signal(address_group_size, contact_group_size):
    """Flag winning vendors that belong to an address or contact group shared with other vendors."""
    return address_group_size > 1 or contact_group_size > 1


def bids_are_close(amount_a, amount_b, threshold=CLOSE_BID_RELATIVE_THRESHOLD):
    """Return True if two bid amounts differ by no more than `threshold` of their average."""
    average = (amount_a + amount_b) / 2
    if average <= 0:
        return False
    return abs(amount_a - amount_b) <= threshold * average


def detect_unusual_bid_pattern(non_winning_amounts):
    """Flag a tender if any two non-winning bids are extremely close to each other."""
    for i in range(len(non_winning_amounts)):
        for j in range(i + 1, len(non_winning_amounts)):
            if bids_are_close(non_winning_amounts[i], non_winning_amounts[j]):
                return True
    return False


def compute_unusual_bid_signals(bids_df):
    """Return a dict of tender_id -> unusual_bid_pattern flag, computed from non-winning bids."""
    flags = {}
    for tender_id, group in bids_df.groupby("tender_id"):
        non_winning_amounts = group.loc[~group["is_winner"], "bid_amount"].tolist()
        flags[tender_id] = detect_unusual_bid_pattern(non_winning_amounts)
    return flags


def review_priority_for_score(score):
    """Map a 0-100 score to a review priority label."""
    if score >= 75:
        return "Critical"
    if score >= 50:
        return "High"
    if score >= 25:
        return "Medium"
    return "Low"


def score_tender(high_price_flag, low_competition_flag, new_vendor_flag,
                  shared_relationship_flag, unusual_bid_flag,
                  price_ratio, bid_count, vendor_age_days, vendor_id):
    """Combine the five signals into a score, priority, signal list, and plain-language explanation."""
    score = 0
    signal_names = []
    explanation_parts = []

    if high_price_flag:
        score += WEIGHT_HIGH_PRICE
        signal_names.append("high_price")
        explanation_parts.append(
            f"Contract amount is {price_ratio:.2f}x the estimated value, "
            f"above the {HIGH_PRICE_RATIO_THRESHOLD}x review threshold."
        )

    if low_competition_flag:
        score += WEIGHT_LOW_COMPETITION
        signal_names.append("low_competition")
        explanation_parts.append(f"Only {bid_count} bids were submitted for this tender.")

    if new_vendor_flag:
        score += WEIGHT_NEW_VENDOR
        signal_names.append("new_vendor")
        explanation_parts.append(
            f"Winning vendor {vendor_id} was registered {vendor_age_days} days before "
            f"the tender date, within the {NEW_VENDOR_WINDOW_DAYS}-day recent-registration window."
        )

    if shared_relationship_flag:
        score += WEIGHT_SHARED_RELATIONSHIP
        signal_names.append("shared_relationship")
        explanation_parts.append(
            f"Winning vendor {vendor_id} shares a registered address or contact group "
            f"with at least one other vendor."
        )

    if unusual_bid_flag:
        score += WEIGHT_UNUSUAL_BID_PATTERN
        signal_names.append("unusual_bid_pattern")
        explanation_parts.append(
            "Two or more competing bids were within 0.3% of each other, an unusually narrow spread."
        )

    priority = review_priority_for_score(score)
    explanation = " ".join(explanation_parts) if explanation_parts else "No unusual signals were detected for this tender."
    signals = ";".join(signal_names)

    return score, priority, signals, explanation


def build_scoring_table(vendors_df, tenders_df, bids_df, contracts_df):
    """Build one scoring row per tender using only observed data. Never reads ground truth."""
    bid_counts = bids_df.groupby("tender_id").size().rename("bid_count")
    unusual_bid_flags = compute_unusual_bid_signals(bids_df)
    address_group_sizes = vendors_df.groupby("address_group_id").size()
    contact_group_sizes = vendors_df.groupby("contact_group_id").size()
    vendor_lookup = vendors_df.set_index("vendor_id")

    merged = tenders_df.merge(contracts_df, on="tender_id", how="left")
    merged = merged.merge(bid_counts, on="tender_id", how="left")
    merged["bid_count"] = merged["bid_count"].fillna(0).astype(int)

    rows = []
    for row in merged.itertuples():
        vendor_id = getattr(row, "winning_vendor_id", None)
        vendor = vendor_lookup.loc[vendor_id] if pd.notna(vendor_id) and vendor_id in vendor_lookup.index else None

        estimated_value = row.estimated_value
        contract_amount = getattr(row, "contract_amount", None)

        price_ratio, high_price_flag = compute_high_price_signal(contract_amount, estimated_value)
        low_competition_flag = compute_low_competition_signal(row.bid_count)

        if vendor is not None:
            vendor_age_days, new_vendor_flag = compute_new_vendor_signal(
                row.tender_date, vendor["registration_date"]
            )
            address_group_size = address_group_sizes.get(vendor["address_group_id"], 1)
            contact_group_size = contact_group_sizes.get(vendor["contact_group_id"], 1)
            shared_relationship_flag = compute_shared_relationship_signal(
                address_group_size, contact_group_size
            )
        else:
            vendor_age_days, new_vendor_flag = None, False
            shared_relationship_flag = False

        unusual_bid_flag = unusual_bid_flags.get(row.tender_id, False)

        score, priority, signals, explanation = score_tender(
            high_price_flag, low_competition_flag, new_vendor_flag,
            shared_relationship_flag, unusual_bid_flag,
            price_ratio, row.bid_count, vendor_age_days, vendor_id,
        )

        rows.append({
            "tender_id": row.tender_id,
            "department": row.department,
            "tender_category": row.tender_category,
            "estimated_value": estimated_value,
            "contract_amount": contract_amount,
            "price_ratio": round(price_ratio, 3) if price_ratio is not None else None,
            "bid_count": row.bid_count,
            "winning_vendor_id": vendor_id,
            "vendor_age_days": vendor_age_days,
            "has_shared_relationship": shared_relationship_flag,
            "has_unusual_bid_pattern": unusual_bid_flag,
            "score": score,
            "review_priority": priority,
            "review_candidate": score >= REVIEW_CANDIDATE_MIN_SCORE,
            "signals": signals,
            "explanation": explanation,
        })

    results_df = pd.DataFrame(rows)
    results_df = results_df.sort_values("score", ascending=False).reset_index(drop=True)
    return results_df


def save_scoring_results(results_df):
    """Write the scoring results to data/evaluation/scoring_results.csv and return the path."""
    DATA_EVAL_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_EVAL_DIR / "scoring_results.csv"
    results_df.to_csv(output_path, index=False)
    return output_path


def validate_scoring_results(results_df, tenders_df):
    """
    Run sanity checks on the scoring output.

    Raises an AssertionError with a clear message on the first failed check.
    Returns True if every check passes.
    """
    assert len(results_df) == len(tenders_df), \
        f"Expected {len(tenders_df)} scoring rows, found {len(results_df)}"

    assert results_df["tender_id"].is_unique, "tender_id values must be unique in scoring results"
    assert set(results_df["tender_id"]) == set(tenders_df["tender_id"]), \
        "every tender must have exactly one scoring row"

    assert results_df["score"].between(0, 100).all(), "score must be between 0 and 100"

    assert results_df["review_priority"].isin(VALID_REVIEW_PRIORITIES).all(), \
        f"review_priority must be one of {VALID_REVIEW_PRIORITIES}"

    return True


if __name__ == "__main__":
    vendors_df, tenders_df, bids_df, contracts_df = load_scoring_inputs()

    results_df = build_scoring_table(vendors_df, tenders_df, bids_df, contracts_df)
    output_path = save_scoring_results(results_df)
    print(f"Scored {len(results_df)} tenders -> {output_path}")

    validate_scoring_results(results_df, tenders_df)
    print("scoring_results.csv passed all validation checks")
