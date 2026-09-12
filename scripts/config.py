RANDOM_SEED = 42

NUM_TENDERS = 500
NUM_VENDORS = 120
NUM_DEPARTMENTS = 5

MIN_BIDS_PER_TENDER = 2
MAX_BIDS_PER_TENDER = 8

PLANTED_PATTERN_RATIO = 0.15

# Vendor generation

VENDOR_CATEGORIES = [
    "Construction",
    "IT Services",
    "Medical Supplies",
    "Office Supplies",
    "Consulting",
]

VENDOR_CITIES = [
    "Meridian City",
    "Northgate",
    "Rosedale",
    "Fairhaven",
    "Lakeside",
    "Brookfield",
    "Eastwood",
    "Clearwater",
]

VENDOR_CITY_WEIGHTS = [0.18, 0.15, 0.13, 0.12, 0.11, 0.11, 0.10, 0.10]

REGISTRATION_DATE_START = "2010-01-01"
REGISTRATION_DATE_END = "2024-12-31"

SHARED_GROUP_SIZE = 3
NUM_SHARED_ADDRESS_GROUPS = 4
NUM_SHARED_CONTACT_GROUPS = 4

# Tender generation

DEPARTMENTS = [
    "Public Works",
    "Health",
    "Education",
    "Transport",
    "IT & Digital Services",
]

TENDER_DATE_START = "2021-01-01"
TENDER_DATE_END = "2024-12-31"

SUBMISSION_DEADLINE_MIN_DAYS = 15
SUBMISSION_DEADLINE_MAX_DAYS = 60

PROCUREMENT_METHODS = ["Open Tender", "Limited Tender", "Single Vendor", "Framework Agreement"]
PROCUREMENT_METHOD_WEIGHTS = [0.55, 0.25, 0.10, 0.10]

# category -> (min, max) estimated tender value
TENDER_CATEGORY_VALUE_RANGE = {
    "Construction": (2_000_000, 50_000_000),
    "IT Services": (500_000, 15_000_000),
    "Medical Supplies": (300_000, 10_000_000),
    "Office Supplies": (50_000, 2_000_000),
    "Consulting": (200_000, 8_000_000),
}

# category -> (min, max) contract duration in days
TENDER_CATEGORY_DURATION_RANGE = {
    "Construction": (180, 730),
    "IT Services": (60, 365),
    "Medical Supplies": (30, 180),
    "Office Supplies": (30, 120),
    "Consulting": (30, 365),
}

# Bid and contract generation

BID_AMOUNT_STD_FRACTION = 0.12
BID_AMOUNT_MIN_FRACTION = 0.75
BID_AMOUNT_MAX_FRACTION = 1.35

CONTRACT_AWARD_GAP_MIN_DAYS = 7
CONTRACT_AWARD_GAP_MAX_DAYS = 30

# Planted synthetic patterns (Stage 5)

PATTERN_GROUP_SIZE = 15
MULTI_PATTERN_COUNT = 10

NEW_VENDOR_WINDOW_DAYS = 730

HIGH_PRICE_FACTOR_MIN = 1.3
HIGH_PRICE_FACTOR_MAX = 1.6

CLOSE_BID_MAX_OFFSET = 0.003

CATEGORY_TITLE_NOUNS = {
    "Construction": [
        "Road Construction Project", "Government Building Renovation",
        "Bridge Construction", "Drainage System Upgrade",
    ],
    "IT Services": [
        "IT Infrastructure Upgrade", "Software Development Services",
        "Network Maintenance Services", "Data Center Setup",
    ],
    "Medical Supplies": [
        "Medical Equipment Supply", "Hospital Consumables Supply",
        "Ambulance Procurement", "Pharmaceutical Supply",
    ],
    "Office Supplies": [
        "Office Furniture Supply", "Stationery Supply",
        "Printer and Consumables Supply", "Office Equipment Procurement",
    ],
    "Consulting": [
        "Policy Advisory Services", "Financial Audit Services",
        "Technical Consulting Services", "Training and Capacity Building",
    ],
}
