"""Synthetic dataset generation for ProcureLens. Currently: vendors and tenders."""

from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    RANDOM_SEED,
    NUM_VENDORS,
    NUM_TENDERS,
    VENDOR_CATEGORIES,
    VENDOR_CITIES,
    VENDOR_CITY_WEIGHTS,
    REGISTRATION_DATE_START,
    REGISTRATION_DATE_END,
    SHARED_GROUP_SIZE,
    NUM_SHARED_ADDRESS_GROUPS,
    NUM_SHARED_CONTACT_GROUPS,
    DEPARTMENTS,
    TENDER_DATE_START,
    TENDER_DATE_END,
    SUBMISSION_DEADLINE_MIN_DAYS,
    SUBMISSION_DEADLINE_MAX_DAYS,
    PROCUREMENT_METHODS,
    PROCUREMENT_METHOD_WEIGHTS,
    TENDER_CATEGORY_VALUE_RANGE,
    TENDER_CATEGORY_DURATION_RANGE,
    CATEGORY_TITLE_NOUNS,
    MIN_BIDS_PER_TENDER,
    MAX_BIDS_PER_TENDER,
    BID_AMOUNT_STD_FRACTION,
    BID_AMOUNT_MIN_FRACTION,
    BID_AMOUNT_MAX_FRACTION,
    CONTRACT_AWARD_GAP_MIN_DAYS,
    CONTRACT_AWARD_GAP_MAX_DAYS,
)

DATA_RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

VENDOR_NAME_PREFIXES = [
    "Highland", "Summit", "Anchor", "Vanguard", "Crestline", "Northgate",
    "Silverline", "Bluewave", "Ironclad", "Trueline", "Everest", "Horizon",
    "Unity", "Prime", "Regional", "National", "Sunrise", "Meridian",
    "Cornerstone", "Apex",
]

VENDOR_NAME_SUFFIXES = ["Pvt Ltd", "Ltd", "Group", "& Co.", "Enterprises", "Inc."]

CATEGORY_NAME_NOUNS = {
    "Construction": ["Construction", "Infrastructure", "Builders", "Contractors"],
    "IT Services": ["Systems", "Software", "Technologies", "Solutions"],
    "Medical Supplies": ["Healthcare", "MedSupplies", "Pharma", "Health"],
    "Office Supplies": ["Office Supplies", "Stationery", "Traders", "Supplies"],
    "Consulting": ["Consulting", "Advisory", "Partners", "Associates"],
}


def generate_vendor_ids(num_vendors):
    """Return sequential vendor IDs like VEN0001, VEN0002, ..."""
    return [f"VEN{i:04d}" for i in range(1, num_vendors + 1)]


def generate_vendor_categories(num_vendors, rng):
    """Assign each vendor one category, roughly evenly split."""
    return rng.choice(VENDOR_CATEGORIES, size=num_vendors)


def generate_vendor_names(categories, rng):
    """Build a unique synthetic company name per vendor, hinting at its category."""
    used_names = set()
    names = []
    for category in categories:
        noun_options = CATEGORY_NAME_NOUNS[category]
        while True:
            prefix = rng.choice(VENDOR_NAME_PREFIXES)
            noun = rng.choice(noun_options)
            suffix = rng.choice(VENDOR_NAME_SUFFIXES)
            name = f"{prefix} {noun} {suffix}"
            if name not in used_names:
                used_names.add(name)
                names.append(name)
                break
    return names


def generate_registered_cities(num_vendors, rng):
    """Assign each vendor a registration city; a few cities are more common than others."""
    return rng.choice(VENDOR_CITIES, size=num_vendors, p=VENDOR_CITY_WEIGHTS)


def generate_registration_dates(num_vendors, rng):
    """Assign each vendor a random registration date within the allowed range."""
    start = pd.Timestamp(REGISTRATION_DATE_START)
    end = pd.Timestamp(REGISTRATION_DATE_END)
    total_days = (end - start).days
    offsets = rng.integers(0, total_days + 1, size=num_vendors)
    return [(start + pd.Timedelta(days=int(d))).strftime("%Y-%m-%d") for d in offsets]


def assign_shared_groups(num_vendors, num_shared_groups, group_size, group_prefix, rng):
    """
    Assign every vendor to a group.

    Most vendors get their own singleton group (size 1, shared with no one).
    A small number of vendors are placed into a handful of shared groups of
    exactly `group_size` vendors each, representing vendors that appear to
    share the same registration details.
    """
    group_ids = [None] * num_vendors
    num_shared_vendors = num_shared_groups * group_size

    shared_indices = rng.choice(num_vendors, size=num_shared_vendors, replace=False)

    for group_num in range(num_shared_groups):
        start = group_num * group_size
        chunk = shared_indices[start:start + group_size]
        for idx in chunk:
            group_ids[idx] = f"{group_prefix}_SHARED{group_num + 1}"

    singleton_counter = 1
    for idx in range(num_vendors):
        if group_ids[idx] is None:
            group_ids[idx] = f"{group_prefix}_SOLO{singleton_counter:03d}"
            singleton_counter += 1

    return group_ids


def generate_vendors():
    """Build the full synthetic vendors DataFrame."""
    rng = np.random.default_rng(RANDOM_SEED)

    vendor_ids = generate_vendor_ids(NUM_VENDORS)
    categories = generate_vendor_categories(NUM_VENDORS, rng)
    names = generate_vendor_names(categories, rng)
    cities = generate_registered_cities(NUM_VENDORS, rng)
    registration_dates = generate_registration_dates(NUM_VENDORS, rng)
    address_groups = assign_shared_groups(
        NUM_VENDORS, NUM_SHARED_ADDRESS_GROUPS, SHARED_GROUP_SIZE, "ADDR", rng
    )
    contact_groups = assign_shared_groups(
        NUM_VENDORS, NUM_SHARED_CONTACT_GROUPS, SHARED_GROUP_SIZE, "CONTACT", rng
    )

    return pd.DataFrame({
        "vendor_id": vendor_ids,
        "vendor_name": names,
        "vendor_category": categories,
        "registered_city": cities,
        "registration_date": registration_dates,
        "address_group_id": address_groups,
        "contact_group_id": contact_groups,
    })


def save_vendors(vendors_df):
    """Write the vendors DataFrame to data/raw/vendors.csv and return the path."""
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_RAW_DIR / "vendors.csv"
    vendors_df.to_csv(output_path, index=False)
    return output_path


def generate_tender_ids(num_tenders):
    """Return sequential tender IDs like TEN0001, TEN0002, ..."""
    return [f"TEN{i:04d}" for i in range(1, num_tenders + 1)]


def generate_tender_departments(num_tenders, rng):
    """Assign each tender to one of the fixed departments."""
    return rng.choice(DEPARTMENTS, size=num_tenders)


def generate_tender_categories(num_tenders, rng):
    """Assign each tender a procurement category (same list used for vendors)."""
    return rng.choice(VENDOR_CATEGORIES, size=num_tenders)


def generate_tender_titles(categories, departments, rng):
    """Build a descriptive title from a category-appropriate project noun and the department."""
    titles = []
    for category, department in zip(categories, departments):
        noun = rng.choice(CATEGORY_TITLE_NOUNS[category])
        titles.append(f"{noun} - {department}")
    return titles


def generate_estimated_values(categories, rng):
    """Sample an estimated tender value from the category's realistic value range."""
    values = []
    for category in categories:
        low, high = TENDER_CATEGORY_VALUE_RANGE[category]
        raw_value = rng.uniform(low, high)
        values.append(int(round(raw_value / 1000) * 1000))
    return values


def generate_tender_dates(num_tenders, rng):
    """Assign each tender a random date within the allowed tender-date range."""
    start = pd.Timestamp(TENDER_DATE_START)
    end = pd.Timestamp(TENDER_DATE_END)
    total_days = (end - start).days
    offsets = rng.integers(0, total_days + 1, size=num_tenders)
    return [start + pd.Timedelta(days=int(d)) for d in offsets]


def generate_submission_deadlines(tender_dates, rng):
    """Assign each tender a submission deadline that falls after its tender date."""
    offsets = rng.integers(
        SUBMISSION_DEADLINE_MIN_DAYS, SUBMISSION_DEADLINE_MAX_DAYS + 1, size=len(tender_dates)
    )
    return [date + pd.Timedelta(days=int(offset)) for date, offset in zip(tender_dates, offsets)]


def generate_contract_durations(categories, rng):
    """Sample a contract duration in days from the category's realistic duration range."""
    durations = []
    for category in categories:
        low, high = TENDER_CATEGORY_DURATION_RANGE[category]
        durations.append(int(rng.integers(low, high + 1)))
    return durations


def generate_procurement_methods(num_tenders, rng):
    """Assign each tender a procurement method from the fixed weighted set."""
    return rng.choice(PROCUREMENT_METHODS, size=num_tenders, p=PROCUREMENT_METHOD_WEIGHTS)


def generate_tender_locations(num_tenders, rng):
    """Assign each tender a location, reusing the vendor city list for consistency."""
    return rng.choice(VENDOR_CITIES, size=num_tenders, p=VENDOR_CITY_WEIGHTS)


def generate_tenders():
    """Build the full synthetic tenders DataFrame."""
    rng = np.random.default_rng(RANDOM_SEED + 1)

    tender_ids = generate_tender_ids(NUM_TENDERS)
    departments = generate_tender_departments(NUM_TENDERS, rng)
    categories = generate_tender_categories(NUM_TENDERS, rng)
    titles = generate_tender_titles(categories, departments, rng)
    estimated_values = generate_estimated_values(categories, rng)
    tender_dates = generate_tender_dates(NUM_TENDERS, rng)
    submission_deadlines = generate_submission_deadlines(tender_dates, rng)
    contract_durations = generate_contract_durations(categories, rng)
    procurement_methods = generate_procurement_methods(NUM_TENDERS, rng)
    locations = generate_tender_locations(NUM_TENDERS, rng)

    return pd.DataFrame({
        "tender_id": tender_ids,
        "department": departments,
        "tender_category": categories,
        "tender_title": titles,
        "estimated_value": estimated_values,
        "tender_date": [d.strftime("%Y-%m-%d") for d in tender_dates],
        "submission_deadline": [d.strftime("%Y-%m-%d") for d in submission_deadlines],
        "contract_duration_days": contract_durations,
        "procurement_method": procurement_methods,
        "location": locations,
    })


def save_tenders(tenders_df):
    """Write the tenders DataFrame to data/raw/tenders.csv and return the path."""
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_RAW_DIR / "tenders.csv"
    tenders_df.to_csv(output_path, index=False)
    return output_path


def select_bidding_vendors(tender_category, vendors_df, num_bids, rng):
    """
    Pick `num_bids` distinct vendors to bid on a tender.

    Prefers vendors whose category matches the tender's category (realistic
    eligibility). If that pool is too small, tops it up with vendors from
    other categories so every tender still gets enough bids.
    """
    category_pool = vendors_df.loc[
        vendors_df["vendor_category"] == tender_category, "vendor_id"
    ].to_numpy().copy()
    rng.shuffle(category_pool)

    if len(category_pool) >= num_bids:
        return list(category_pool[:num_bids])

    selected = list(category_pool)
    other_pool = vendors_df.loc[
        ~vendors_df["vendor_id"].isin(selected), "vendor_id"
    ].to_numpy().copy()
    rng.shuffle(other_pool)
    remaining_needed = num_bids - len(selected)
    selected.extend(other_pool[:remaining_needed])
    return selected


def generate_bid_amount(estimated_value, rng):
    """Sample a bid amount that varies realistically around the tender's estimated value."""
    factor = rng.normal(1.0, BID_AMOUNT_STD_FRACTION)
    factor = min(max(factor, BID_AMOUNT_MIN_FRACTION), BID_AMOUNT_MAX_FRACTION)
    raw_amount = estimated_value * factor
    return int(round(raw_amount / 1000) * 1000)


def generate_submission_time(tender_date, submission_deadline, rng):
    """Pick a random submission timestamp between the tender date and its deadline."""
    total_days = (submission_deadline - tender_date).days
    day_offset = int(rng.integers(0, total_days + 1))
    hour = int(rng.integers(9, 18))
    minute = int(rng.integers(0, 60))
    second = int(rng.integers(0, 60))
    timestamp = tender_date + pd.Timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)
    return min(timestamp, submission_deadline)


def generate_bids(vendors_df, tenders_df, rng):
    """Build the full synthetic bids DataFrame, 2-8 bids per tender with exactly one winner each."""
    rows = []
    bid_counter = 1

    for tender in tenders_df.itertuples():
        num_bids = int(rng.integers(MIN_BIDS_PER_TENDER, MAX_BIDS_PER_TENDER + 1))
        bidding_vendor_ids = select_bidding_vendors(
            tender.tender_category, vendors_df, num_bids, rng
        )

        tender_date = pd.Timestamp(tender.tender_date)
        submission_deadline = pd.Timestamp(tender.submission_deadline)

        tender_bids = []
        for vendor_id in bidding_vendor_ids:
            bid_amount = generate_bid_amount(tender.estimated_value, rng)
            submission_time = generate_submission_time(tender_date, submission_deadline, rng)
            tender_bids.append({
                "bid_id": f"BID{bid_counter:06d}",
                "tender_id": tender.tender_id,
                "vendor_id": vendor_id,
                "bid_amount": bid_amount,
                "submission_time": submission_time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            bid_counter += 1

        winning_bid = min(tender_bids, key=lambda bid: bid["bid_amount"])
        for bid in tender_bids:
            bid["is_winner"] = bid is winning_bid
        rows.extend(tender_bids)

    return pd.DataFrame(rows)


def save_bids(bids_df):
    """Write the bids DataFrame to data/raw/bids.csv and return the path."""
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_RAW_DIR / "bids.csv"
    bids_df.to_csv(output_path, index=False)
    return output_path


def generate_contracts(bids_df, tenders_df, rng):
    """Build one contract per tender from its winning bid."""
    winning_bids = bids_df[bids_df["is_winner"]].set_index("tender_id")
    tenders_indexed = tenders_df.set_index("tender_id")

    rows = []
    for contract_num, tender_id in enumerate(tenders_df["tender_id"], start=1):
        winning_bid = winning_bids.loc[tender_id]
        tender = tenders_indexed.loc[tender_id]

        submission_deadline = pd.Timestamp(tender["submission_deadline"])
        award_gap_days = int(rng.integers(CONTRACT_AWARD_GAP_MIN_DAYS, CONTRACT_AWARD_GAP_MAX_DAYS + 1))
        start_date = submission_deadline + pd.Timedelta(days=award_gap_days)
        end_date = start_date + pd.Timedelta(days=int(tender["contract_duration_days"]))

        rows.append({
            "contract_id": f"CON{contract_num:04d}",
            "tender_id": tender_id,
            "winning_vendor_id": winning_bid["vendor_id"],
            "contract_amount": winning_bid["bid_amount"],
            "contract_start_date": start_date.strftime("%Y-%m-%d"),
            "contract_end_date": end_date.strftime("%Y-%m-%d"),
        })

    return pd.DataFrame(rows)


def save_contracts(contracts_df):
    """Write the contracts DataFrame to data/raw/contracts.csv and return the path."""
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_RAW_DIR / "contracts.csv"
    contracts_df.to_csv(output_path, index=False)
    return output_path


if __name__ == "__main__":
    vendors_df = generate_vendors()
    vendors_path = save_vendors(vendors_df)
    print(f"Generated {len(vendors_df)} vendors -> {vendors_path}")

    tenders_df = generate_tenders()
    tenders_path = save_tenders(tenders_df)
    print(f"Generated {len(tenders_df)} tenders -> {tenders_path}")

    vendors_df = pd.read_csv(DATA_RAW_DIR / "vendors.csv")
    tenders_df = pd.read_csv(DATA_RAW_DIR / "tenders.csv")

    bids_rng = np.random.default_rng(RANDOM_SEED + 2)
    bids_df = generate_bids(vendors_df, tenders_df, bids_rng)
    bids_path = save_bids(bids_df)
    print(f"Generated {len(bids_df)} bids -> {bids_path}")

    contracts_rng = np.random.default_rng(RANDOM_SEED + 3)
    contracts_df = generate_contracts(bids_df, tenders_df, contracts_rng)
    contracts_path = save_contracts(contracts_df)
    print(f"Generated {len(contracts_df)} contracts -> {contracts_path}")
