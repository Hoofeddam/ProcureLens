"""
Plant explainable synthetic anomaly patterns into the generated procurement data.

Reads the existing vendors/tenders/bids/contracts, modifies only bid and
contract values to introduce ~75 planted tender cases, writes the updated
bids/contracts back to data/raw/, and writes the evaluation-only labels to
data/evaluation/ground_truth.csv. Vendors and tenders are never modified.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    RANDOM_SEED,
    PATTERN_GROUP_SIZE,
    MULTI_PATTERN_COUNT,
    NEW_VENDOR_WINDOW_DAYS,
    HIGH_PRICE_FACTOR_MIN,
    HIGH_PRICE_FACTOR_MAX,
    CLOSE_BID_MAX_OFFSET,
)

DATA_RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
DATA_EVAL_DIR = Path(__file__).resolve().parent.parent / "data" / "evaluation"

PATTERN_HIGH_PRICE = "high_price"
PATTERN_LOW_COMPETITION = "low_competition"
PATTERN_NEW_VENDOR = "new_vendor_winner"
PATTERN_SHARED_VENDOR = "shared_vendor_relationship"
PATTERN_UNUSUAL_BID = "unusual_bid_pattern"


def load_raw_tables():
    """Load the current vendors, tenders, bids, and contracts tables from data/raw/."""
    vendors_df = pd.read_csv(DATA_RAW_DIR / "vendors.csv")
    tenders_df = pd.read_csv(DATA_RAW_DIR / "tenders.csv")
    bids_df = pd.read_csv(DATA_RAW_DIR / "bids.csv")
    contracts_df = pd.read_csv(DATA_RAW_DIR / "contracts.csv")
    return vendors_df, tenders_df, bids_df, contracts_df


def compute_bid_count_ge3_pool(bids_df):
    """Tenders that currently have 3 or more bids (needed to trim or to cluster non-winners)."""
    counts = bids_df.groupby("tender_id").size()
    return counts[counts >= 3].index.to_numpy()


def compute_new_vendor_pool(bids_df, vendors_df, tenders_df):
    """Tenders where at least one current bidder registered within NEW_VENDOR_WINDOW_DAYS of the tender date."""
    merged = bids_df.merge(vendors_df[["vendor_id", "registration_date"]], on="vendor_id")
    merged = merged.merge(tenders_df[["tender_id", "tender_date"]], on="tender_id")
    days_since_registration = (
        pd.to_datetime(merged["tender_date"]) - pd.to_datetime(merged["registration_date"])
    ).dt.days
    eligible = merged.loc[
        (days_since_registration >= 0) & (days_since_registration <= NEW_VENDOR_WINDOW_DAYS)
    ]
    return eligible["tender_id"].unique()


def compute_shared_vendor_pool(bids_df, vendors_df):
    """Tenders where at least one current bidder belongs to a shared address or contact group."""
    merged = bids_df.merge(
        vendors_df[["vendor_id", "address_group_id", "contact_group_id"]], on="vendor_id"
    )
    eligible = merged.loc[
        merged["address_group_id"].str.contains("SHARED")
        | merged["contact_group_id"].str.contains("SHARED")
    ]
    return eligible["tender_id"].unique()


def sample_disjoint(pool, count, used_tender_ids, rng):
    """Randomly pick `count` tenders from `pool`, excluding any already in `used_tender_ids`."""
    available = np.array([t for t in pool if t not in used_tender_ids])
    rng.shuffle(available)
    chosen = list(available[:count])
    used_tender_ids.update(chosen)
    return chosen


def apply_high_price_pattern(tender_id, bids_df, contracts_df, tenders_df, rng):
    """Inflate the current winning bid/contract amount well above the tender's estimated value."""
    estimated_value = tenders_df.loc[tenders_df["tender_id"] == tender_id, "estimated_value"].iloc[0]
    winner_mask = (bids_df["tender_id"] == tender_id) & (bids_df["is_winner"])

    factor = rng.uniform(HIGH_PRICE_FACTOR_MIN, HIGH_PRICE_FACTOR_MAX)
    new_amount = int(round(estimated_value * factor / 1000) * 1000)

    bids_df.loc[winner_mask, "bid_amount"] = new_amount
    contracts_df.loc[contracts_df["tender_id"] == tender_id, "contract_amount"] = new_amount

    return (
        f"Winning amount of {new_amount:,} is about {factor:.2f}x the estimated "
        f"value of {estimated_value:,}."
    )


def apply_low_competition_pattern(tender_id, bids_df, rng):
    """Trim a tender's bids down to exactly 2: the winner plus one other, chosen at random."""
    tender_bids = bids_df[bids_df["tender_id"] == tender_id]
    non_winner_ids = tender_bids.loc[~tender_bids["is_winner"], "bid_id"].to_numpy().copy()
    rng.shuffle(non_winner_ids)

    drop_bid_ids = set(non_winner_ids[1:])
    bids_df.drop(index=bids_df[bids_df["bid_id"].isin(drop_bid_ids)].index, inplace=True)

    return "Only 2 vendors submitted bids for this tender, indicating very low competition."


def apply_new_vendor_pattern(tender_id, bids_df, vendors_df, tenders_df, contracts_df):
    """Make sure the tender's winner is a vendor registered within the last 2 years of the tender date."""
    tender_date = pd.Timestamp(tenders_df.loc[tenders_df["tender_id"] == tender_id, "tender_date"].iloc[0])

    tender_bids = bids_df[bids_df["tender_id"] == tender_id].merge(
        vendors_df[["vendor_id", "registration_date"]], on="vendor_id"
    )
    tender_bids["registration_date"] = pd.to_datetime(tender_bids["registration_date"])
    tender_bids["days_since_registration"] = (tender_date - tender_bids["registration_date"]).dt.days

    eligible = tender_bids[
        (tender_bids["days_since_registration"] >= 0)
        & (tender_bids["days_since_registration"] <= NEW_VENDOR_WINDOW_DAYS)
    ].sort_values("days_since_registration")

    current_winner = tender_bids[tender_bids["is_winner"]].iloc[0]

    if current_winner["bid_id"] in eligible["bid_id"].to_numpy():
        chosen = current_winner
    else:
        chosen = eligible.iloc[0]
        bids_df.loc[bids_df["bid_id"] == current_winner["bid_id"], "is_winner"] = False
        bids_df.loc[bids_df["bid_id"] == chosen["bid_id"], "is_winner"] = True
        contracts_df.loc[contracts_df["tender_id"] == tender_id, "winning_vendor_id"] = chosen["vendor_id"]
        contracts_df.loc[contracts_df["tender_id"] == tender_id, "contract_amount"] = chosen["bid_amount"]

    return (
        f"Winning vendor {chosen['vendor_id']} was registered on "
        f"{chosen['registration_date'].date()}, within 2 years of the tender date "
        f"{tender_date.date()}."
    )


def apply_shared_vendor_pattern(tender_id, bids_df, vendors_df, contracts_df):
    """Make sure the tender's winner belongs to a shared address or contact group."""
    tender_bids = bids_df[bids_df["tender_id"] == tender_id].merge(
        vendors_df[["vendor_id", "address_group_id", "contact_group_id"]], on="vendor_id"
    )
    eligible = tender_bids[
        tender_bids["address_group_id"].str.contains("SHARED")
        | tender_bids["contact_group_id"].str.contains("SHARED")
    ]

    current_winner = tender_bids[tender_bids["is_winner"]].iloc[0]

    if current_winner["bid_id"] in eligible["bid_id"].to_numpy():
        chosen = current_winner
    else:
        chosen = eligible.iloc[0]
        bids_df.loc[bids_df["bid_id"] == current_winner["bid_id"], "is_winner"] = False
        bids_df.loc[bids_df["bid_id"] == chosen["bid_id"], "is_winner"] = True
        contracts_df.loc[contracts_df["tender_id"] == tender_id, "winning_vendor_id"] = chosen["vendor_id"]
        contracts_df.loc[contracts_df["tender_id"] == tender_id, "contract_amount"] = chosen["bid_amount"]

    shared_group = (
        chosen["address_group_id"]
        if "SHARED" in chosen["address_group_id"]
        else chosen["contact_group_id"]
    )
    return (
        f"Winning vendor {chosen['vendor_id']} shares a registration group "
        f"({shared_group}) with other vendors in the dataset."
    )


def apply_unusual_bid_pattern(tender_id, bids_df, rng):
    """Force two of a tender's non-winning bids to land within a very narrow price range."""
    tender_bids = bids_df[bids_df["tender_id"] == tender_id]
    non_winner_ids = tender_bids.loc[~tender_bids["is_winner"], "bid_id"].to_numpy().copy()
    rng.shuffle(non_winner_ids)
    cluster_ids = non_winner_ids[:2]

    base_amount = bids_df.loc[bids_df["bid_id"] == cluster_ids[0], "bid_amount"].iloc[0]
    for bid_id in cluster_ids:
        offset = rng.uniform(-CLOSE_BID_MAX_OFFSET, CLOSE_BID_MAX_OFFSET)
        new_amount = int(round(base_amount * (1 + offset) / 1000) * 1000)
        bids_df.loc[bids_df["bid_id"] == bid_id, "bid_amount"] = new_amount

    return "Two competing bids were submitted within a very narrow price range of each other."


def plant_all_patterns(vendors_df, tenders_df, bids_df, contracts_df, rng):
    """
    Select ~75 tenders and plant one of five explainable patterns into each,
    with a subset getting a second pattern layered on top.

    Returns a dict of tender_id -> {"patterns": [...], "descriptions": [...]}.
    """
    all_tender_ids = tenders_df["tender_id"].to_numpy()
    pool_ge3 = compute_bid_count_ge3_pool(bids_df)
    pool_new_vendor = compute_new_vendor_pool(bids_df, vendors_df, tenders_df)
    pool_shared_vendor = compute_shared_vendor_pool(bids_df, vendors_df)

    used_tender_ids = set()
    high_price_group = sample_disjoint(all_tender_ids, PATTERN_GROUP_SIZE, used_tender_ids, rng)
    low_competition_group = sample_disjoint(pool_ge3, PATTERN_GROUP_SIZE, used_tender_ids, rng)
    new_vendor_group = sample_disjoint(pool_new_vendor, PATTERN_GROUP_SIZE, used_tender_ids, rng)
    shared_vendor_group = sample_disjoint(pool_shared_vendor, PATTERN_GROUP_SIZE, used_tender_ids, rng)
    unusual_bid_group = sample_disjoint(pool_ge3, PATTERN_GROUP_SIZE, used_tender_ids, rng)

    results = {tid: {"patterns": [], "descriptions": []} for tid in used_tender_ids}

    for tender_id in new_vendor_group:
        description = apply_new_vendor_pattern(tender_id, bids_df, vendors_df, tenders_df, contracts_df)
        results[tender_id]["patterns"].append(PATTERN_NEW_VENDOR)
        results[tender_id]["descriptions"].append(description)

    for tender_id in shared_vendor_group:
        description = apply_shared_vendor_pattern(tender_id, bids_df, vendors_df, contracts_df)
        results[tender_id]["patterns"].append(PATTERN_SHARED_VENDOR)
        results[tender_id]["descriptions"].append(description)

    for tender_id in high_price_group:
        description = apply_high_price_pattern(tender_id, bids_df, contracts_df, tenders_df, rng)
        results[tender_id]["patterns"].append(PATTERN_HIGH_PRICE)
        results[tender_id]["descriptions"].append(description)

    for tender_id in unusual_bid_group:
        description = apply_unusual_bid_pattern(tender_id, bids_df, rng)
        results[tender_id]["patterns"].append(PATTERN_UNUSUAL_BID)
        results[tender_id]["descriptions"].append(description)

    for tender_id in low_competition_group:
        description = apply_low_competition_pattern(tender_id, bids_df, rng)
        results[tender_id]["patterns"].append(PATTERN_LOW_COMPETITION)
        results[tender_id]["descriptions"].append(description)

    multi_pattern_pool = np.array(low_competition_group + new_vendor_group + shared_vendor_group + unusual_bid_group)
    rng.shuffle(multi_pattern_pool)
    multi_pattern_tenders = multi_pattern_pool[:MULTI_PATTERN_COUNT]
    for tender_id in multi_pattern_tenders:
        description = apply_high_price_pattern(tender_id, bids_df, contracts_df, tenders_df, rng)
        results[tender_id]["patterns"].append(PATTERN_HIGH_PRICE)
        results[tender_id]["descriptions"].append(description)

    return results


def build_ground_truth(tenders_df, planted_results):
    """Build the evaluation-only ground-truth table covering all tenders."""
    rows = []
    for tender_id in tenders_df["tender_id"]:
        if tender_id in planted_results:
            rows.append({
                "tender_id": tender_id,
                "is_planted_anomaly": True,
                "pattern_types": ";".join(planted_results[tender_id]["patterns"]),
                "pattern_description": "; ".join(planted_results[tender_id]["descriptions"]),
            })
        else:
            rows.append({
                "tender_id": tender_id,
                "is_planted_anomaly": False,
                "pattern_types": "",
                "pattern_description": "",
            })
    return pd.DataFrame(rows)


def save_updated_tables(bids_df, contracts_df, ground_truth_df):
    """Write the modified bids/contracts back to data/raw/ and the labels to data/evaluation/."""
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    DATA_EVAL_DIR.mkdir(parents=True, exist_ok=True)

    bids_path = DATA_RAW_DIR / "bids.csv"
    contracts_path = DATA_RAW_DIR / "contracts.csv"
    ground_truth_path = DATA_EVAL_DIR / "ground_truth.csv"

    bids_df.to_csv(bids_path, index=False)
    contracts_df.to_csv(contracts_path, index=False)
    ground_truth_df.to_csv(ground_truth_path, index=False)

    return bids_path, contracts_path, ground_truth_path


if __name__ == "__main__":
    vendors_df, tenders_df, bids_df, contracts_df = load_raw_tables()

    rng = np.random.default_rng(RANDOM_SEED + 100)
    planted_results = plant_all_patterns(vendors_df, tenders_df, bids_df, contracts_df, rng)
    ground_truth_df = build_ground_truth(tenders_df, planted_results)

    bids_path, contracts_path, ground_truth_path = save_updated_tables(bids_df, contracts_df, ground_truth_df)

    print(f"Planted patterns into {len(planted_results)} tenders")
    print(f"Updated bids -> {bids_path}")
    print(f"Updated contracts -> {contracts_path}")
    print(f"Ground truth -> {ground_truth_path}")
